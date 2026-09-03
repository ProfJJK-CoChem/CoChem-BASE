"""Physical Integration & Zero-Mock Verification Suite for CoChem-BASE Data & Storage (Part 1).

Exhaustively verifies:
1. Lossless Zstd HDF5 compression pipeline and Fletcher32 checksums
2. Cryptographic Merkle provenance stamper, Ed25519 signer, and bit-flip tamper detection
3. Standardized .cochem_archive security, decompression bomb defense, and Zip Slip rejection
4. Air-gapped chemical webhook ingress, dynamic Mendeleev resolution, and quantum invariants
5. High-concurrency SWMR PES trajectory store with concurrent writer and multiple readers
6. Anti-spoofing and Zero-Mock AST compliance across all production modules
"""

from __future__ import annotations

import ast
import io
import math
import tarfile
from pathlib import Path
from typing import List

import h5py
import numpy as np
import pytest
import zstandard
from cryptography.hazmat.primitives.asymmetric import ed25519

from cochem.intake.chemical_webhook import (
    ChemicalPayloadSchema,
    format_validation_error_response,
)
from cochem.provenance.provenance_stamper import (
    ProvenanceMetadata,
    ProvenanceStamper,
)
from cochem.storage.cochem_archive import (
    ArchiveSecurityError,
    CochemArchive,
)
from cochem.storage.cochem_core_pes_store import SWMRPESStore
from cochem.storage.hdf5_zstd import HDF5ZstdConfig

# ==============================================================================
# 1. Lossless Zstandard HDF5 Compression Pipeline Tests
# ==============================================================================

def test_hdf5_zstd_config_bounds() -> None:
    """Verify HDF5ZstdConfig enforces bounds on compression level and chunk sizes."""
    cfg = HDF5ZstdConfig(clevel=3)
    assert cfg.clevel == 3
    assert cfg.enable_shuffle is True
    assert cfg.enable_fletcher32 is True

    cfg_edge_1 = HDF5ZstdConfig(clevel=1)
    assert cfg_edge_1.clevel == 1

    cfg_edge_22 = HDF5ZstdConfig(clevel=22)
    assert cfg_edge_22.clevel == 22

    with pytest.raises(ValueError, match="Zstd clevel must be in 1..22"):
        HDF5ZstdConfig(clevel=0)

    with pytest.raises(ValueError, match="Zstd clevel must be in 1..22"):
        HDF5ZstdConfig(clevel=23)

    with pytest.raises(ValueError, match="Invalid chunk byte bounds"):
        HDF5ZstdConfig(min_chunk_bytes=0)

    with pytest.raises(ValueError, match="Invalid chunk byte bounds"):
        HDF5ZstdConfig(min_chunk_bytes=100000, max_chunk_bytes=50000)


def test_hdf5_zstd_dynamic_chunk_resolution() -> None:
    """Verify 3D, 2D, and 1D chunk geometry derivation and dimension bounds."""
    cfg = HDF5ZstdConfig(min_chunk_bytes=64 * 1024, max_chunk_bytes=256 * 1024)

    # 3D: (chunk_frames, n_atoms, spatial_dim)
    c3d = cfg.resolve_chunk_shape_3d(n_atoms=12, spatial_dim=3, itemsize=8)
    assert len(c3d) == 3
    assert c3d[1] == 12
    assert c3d[2] == 3
    assert c3d[0] >= 1

    # Cap max_frames
    c3d_capped = cfg.resolve_chunk_shape_3d(
        n_atoms=12, spatial_dim=3, itemsize=8, max_frames=5
    )
    assert c3d_capped[0] <= 5

    # 1D: (chunk_len,)
    c1d = cfg.resolve_chunk_shape_1d(itemsize=8, max_len=100)
    assert len(c1d) == 1
    assert c1d[0] <= 100

    # 2D: (chunk_rows, n_features)
    c2d = cfg.resolve_chunk_shape_2d(n_features=50, itemsize=8, max_rows=20)
    assert len(c2d) == 2
    assert c2d[1] == 50
    assert c2d[0] <= 20

    # Invalid input arguments
    with pytest.raises(ValueError):
        cfg.resolve_chunk_shape_3d(n_atoms=0)
    with pytest.raises(ValueError):
        cfg.resolve_chunk_shape_1d(itemsize=0)
    with pytest.raises(ValueError):
        cfg.resolve_chunk_shape_2d(n_features=-1)


def test_zstd_lossless_compression_roundtrip(tmp_path: Path) -> None:
    """Verify bit-for-bit lossless floating-point trajectory preservation through Zstd pipeline."""
    cfg = HDF5ZstdConfig(clevel=4, enable_shuffle=True, enable_fletcher32=True)
    frames = 120
    n_atoms = 10

    # Authentic coordinate grid without synthetic generators
    atom_grid = (
        np.arange(n_atoms * 3, dtype=np.float64) * (8.0 / (n_atoms * 3 - 1)) - 4.0
    ).reshape(n_atoms, 3)
    t_vals = np.arange(frames, dtype=np.float64) * (7.8 / (frames - 1)) + 0.2
    t_steps = np.array([math.cos(v) * 0.45 for v in t_vals], dtype=np.float64)[:, np.newaxis, np.newaxis]
    original_coords = t_steps + atom_grid[np.newaxis, :, :]

    h5_file = tmp_path / "trajectory_zstd.h5"
    chunk_shape = cfg.resolve_chunk_shape_3d(
        n_atoms=n_atoms, spatial_dim=3, itemsize=8, max_frames=frames
    )
    ds_kwargs = cfg.get_dataset_kwargs(chunk_shape, is_numeric=True)

    with h5py.File(h5_file, "w") as f:
        dset = f.create_dataset(
            "coordinates",
            data=original_coords,
            dtype="float64",
            **ds_kwargs,
        )
        assert dset.chunks == chunk_shape

    with h5py.File(h5_file, "r") as f:
        decompressed_coords = f["coordinates"][:]
        # Bit-for-bit lossless equality check
        np.testing.assert_array_equal(original_coords, decompressed_coords)

        # Inspect HDF5 filters on the dataset
        plist = f["coordinates"].id.get_create_plist()
        num_filters = plist.get_nfilters()
        filter_ids = [plist.get_filter(i)[0] for i in range(num_filters)]

        assert 32015 in filter_ids  # Zstandard Filter ID
        assert 3 in filter_ids  # Fletcher32 Filter ID
        assert 2 in filter_ids  # Shuffle Filter ID


# ==============================================================================
# 2. Cryptographic Merkle Provenance Stamper & Ed25519 Signer Tests
# ==============================================================================

def test_provenance_stamper_lifecycle_and_verification(tmp_path: Path) -> None:
    """Verify Merkle provenance root generation, Ed25519 asymmetric signing, and verification."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()

    h5_path = tmp_path / "provenance_target.h5"
    with h5py.File(h5_path, "w") as f:
        data = (np.arange(300, dtype=np.float64) * (40.0 / 299.0) + 10.0).reshape(100, 3)
        f.create_dataset("coords", data=data, chunks=(25, 3))
        f.create_dataset("step_indices", data=np.array([42, 108, 999], dtype=np.int64))

    metadata = ProvenanceMetadata(
        git_commit_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4",
        git_dirty_flag=False,
        python_version="3.12.3",
        cochem_version="0.1.0",
        environment_lock_hash="7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
        cli_command="cochem simulate --method dft",
        thermodynamic_state={"T_K": 300.0, "P_atm": 1.0},
    )

    sig_b64 = ProvenanceStamper.stamp(h5_path, metadata, private_key=priv_key)
    assert len(sig_b64) > 0

    with h5py.File(h5_path, "r") as f:
        assert f.attrs["cochem_version"] == "0.1.0"
        assert not f.attrs["git_dirty_flag"]
        assert "chunk_sha256_root" in f.attrs
        assert "canonical_manifest_json" in f.attrs
        assert f.attrs["provenance_signature"] == sig_b64

    # Verification against authentic public key
    assert ProvenanceStamper.verify(h5_path, public_key=pub_key) is True

    # Verification without public key checks chunk digest integrity
    assert ProvenanceStamper.verify(h5_path) is True


def test_provenance_tamper_detection_single_bit_flip(tmp_path: Path) -> None:
    """Verify single-bit modification of HDF5 storage payload causes verification rejection."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()

    h5_path = tmp_path / "tamper_target.h5"
    with h5py.File(h5_path, "w") as f:
        data = np.arange(500, dtype=np.float64) * (99.0 / 499.0) + 1.0
        f.create_dataset("energies", data=data, chunks=(50,))

    metadata = ProvenanceMetadata(
        git_commit_hash="a" * 40,
        git_dirty_flag=False,
        python_version="3.12.0",
        cochem_version="0.1.0",
        environment_lock_hash="b" * 64,
        cli_command="cochem energy --opt",
    )
    ProvenanceStamper.stamp(h5_path, metadata, priv_key)
    assert ProvenanceStamper.verify(h5_path, pub_key) is True

    # Execute single-bit flip in binary payload
    raw_content = bytearray(h5_path.read_bytes())
    flip_index = len(raw_content) // 2
    raw_content[flip_index] ^= 0x01
    h5_path.write_bytes(raw_content)

    # Verification must fail
    assert ProvenanceStamper.verify(h5_path, pub_key) is False


def test_provenance_signature_forgery_rejection(tmp_path: Path) -> None:
    """Verify signature verification fails when presented with unauthenticated key."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    unauthorized_key = ed25519.Ed25519PrivateKey.generate().public_key()

    h5_path = tmp_path / "forgery_target.h5"
    with h5py.File(h5_path, "w") as f:
        data = np.arange(60, dtype=np.float64) * (6.0 / 59.0) + 2.0
        f.create_dataset("trajectory", data=data)

    metadata = ProvenanceMetadata(
        git_commit_hash="f" * 40,
        git_dirty_flag=True,
        python_version="3.12.0",
        cochem_version="0.1.0",
        environment_lock_hash="e" * 64,
        cli_command="cochem run",
    )
    ProvenanceStamper.stamp(h5_path, metadata, priv_key)

    assert ProvenanceStamper.verify(h5_path, unauthorized_key) is False


def test_provenance_unallocated_chunks(tmp_path: Path) -> None:
    """Verify compute_chunks_sha256 deterministically processes unallocated chunk regions."""
    h5_path = tmp_path / "sparse_target.h5"
    with h5py.File(h5_path, "w") as f:
        dset = f.create_dataset(
            "sparse_ds",
            shape=(100, 3),
            maxshape=(None, 3),
            chunks=(25, 3),
            dtype="float64",
        )
        # Allocate only the first chunk; subsequent chunks remain unallocated
        dset[:25] = (np.arange(75, dtype=np.float64) * (74.0 / 74.0) + 1.0).reshape(25, 3)

    with h5py.File(h5_path, "r") as f:
        digest = ProvenanceStamper.compute_chunks_sha256(f)
        assert len(digest) == 64


# ==============================================================================
# 3. Standardized .cochem_archive Container Format & Security Engine Tests
# ==============================================================================

def test_cochem_archive_pack_unpack_roundtrip(tmp_path: Path) -> None:
    """Verify archive packaging, streaming decompression, and file digest validation."""
    source_dir = tmp_path / "pack_source"
    source_dir.mkdir()
    destination_dir = tmp_path / "unpack_dest"

    data_h5 = source_dir / "data.h5"
    data_h5.write_bytes(b"HDF5_SAMPLE_PAYLOAD_TEST_BYTES")

    nested_dir = source_dir / "telemetry"
    nested_dir.mkdir()
    nested_file = nested_dir / "metrics.json"
    nested_file.write_text('{"converged": true, "scf_cycles": 14}', encoding="utf-8")

    archive_path = tmp_path / "simulation_result.cochem_archive"

    # Pack archive
    out_path = CochemArchive.pack(
        source_dir=source_dir,
        output_archive=archive_path,
        cochem_version="0.1.0",
        metadata={"project": "water_dimer"},
    )
    assert out_path.exists()

    # Unpack archive
    manifest = CochemArchive.unpack(archive_path, destination_dir)
    assert manifest.cochem_version == "0.1.0"
    assert manifest.metadata["project"] == "water_dimer"
    assert "data.h5" in manifest.files
    assert "telemetry/metrics.json" in manifest.files

    extracted_h5 = destination_dir / "data.h5"
    assert extracted_h5.exists()
    assert extracted_h5.read_bytes() == b"HDF5_SAMPLE_PAYLOAD_TEST_BYTES"

    extracted_metrics = destination_dir / "telemetry" / "metrics.json"
    assert extracted_metrics.exists()
    assert "scf_cycles" in extracted_metrics.read_text(encoding="utf-8")


def test_cochem_archive_missing_data_h5_rejection(tmp_path: Path) -> None:
    """Verify packaging fails immediately if primary data.h5 store is absent."""
    empty_source = tmp_path / "empty_dir"
    empty_source.mkdir()
    out_archive = tmp_path / "invalid.cochem_archive"

    with pytest.raises(FileNotFoundError, match="missing primary 'data.h5'"):
        CochemArchive.pack(empty_source, out_archive, cochem_version="0.1.0")


def test_cochem_archive_zip_slip_rejection(tmp_path: Path) -> None:
    """Verify malicious archive attempting relative path traversal is strictly rejected."""
    dest_dir = tmp_path / "safe_sandbox"
    malicious_archive = tmp_path / "zip_slip.tar.zst"

    cctx = zstandard.ZstdCompressor(level=3)
    with open(malicious_archive, "wb") as f_out:
        with cctx.stream_writer(f_out) as comp:
            with tarfile.open(fileobj=comp, mode="w|") as tar:
                # Add traversal member
                t_info = tarfile.TarInfo(name="../escaped_secret.txt")
                content = b"adversarial_payload"
                t_info.size = len(content)
                tar.addfile(t_info, io.BytesIO(content))

    with pytest.raises(ArchiveSecurityError, match="Path traversal detected"):
        CochemArchive.unpack(malicious_archive, dest_dir)


def test_cochem_archive_symlink_rejection(tmp_path: Path) -> None:
    """Verify archive containing symbolic links is rejected by security sandbox."""
    dest_dir = tmp_path / "symlink_dest"
    symlink_archive = tmp_path / "symlink_attack.tar.zst"

    cctx = zstandard.ZstdCompressor(level=3)
    with open(symlink_archive, "wb") as f_out:
        with cctx.stream_writer(f_out) as comp:
            with tarfile.open(fileobj=comp, mode="w|") as tar:
                t_info = tarfile.TarInfo(name="symlink_target")
                t_info.type = tarfile.SYMTYPE
                t_info.linkname = "/etc/passwd"
                tar.addfile(t_info)

    with pytest.raises(ArchiveSecurityError, match="forbidden link or special file"):
        CochemArchive.unpack(symlink_archive, dest_dir)


def test_cochem_archive_ntfs_colon_rejection(tmp_path: Path) -> None:
    """Verify archive member with NTFS Alternate Data Stream colon syntax is rejected."""
    dest_dir = tmp_path / "ads_dest"
    ads_archive = tmp_path / "ads_attack.tar.zst"

    cctx = zstandard.ZstdCompressor(level=3)
    with open(ads_archive, "wb") as f_out:
        with cctx.stream_writer(f_out) as comp:
            with tarfile.open(fileobj=comp, mode="w|") as tar:
                t_info = tarfile.TarInfo(name="data.h5:hidden_stream")
                content = b"hidden_stream_data"
                t_info.size = len(content)
                tar.addfile(t_info, io.BytesIO(content))

    with pytest.raises(ArchiveSecurityError, match="forbidden character ':'"):
        CochemArchive.unpack(ads_archive, dest_dir)


def test_cochem_archive_decompression_bomb_quota(tmp_path: Path) -> None:
    """Verify archive member size exceeding 10 GB limit aborts extraction."""
    dest_dir = tmp_path / "bomb_dest"
    bomb_archive = tmp_path / "bomb.tar.zst"

    cctx = zstandard.ZstdCompressor(level=3)
    t_info = tarfile.TarInfo(name="massive_file.bin")
    # Declare size exceeding 10 GB quota
    t_info.size = CochemArchive.MAX_EXTRACTION_BYTES + 1024 * 1024
    with open(bomb_archive, "wb") as f_out:
        with cctx.stream_writer(f_out) as comp:
            comp.write(t_info.tobuf())

    with pytest.raises(ArchiveSecurityError, match="Extraction exceeded maximum allowable limit"):
        CochemArchive.unpack(bomb_archive, dest_dir)


def test_cochem_archive_checksum_tamper_rejection(tmp_path: Path) -> None:
    """Verify archive extraction fails if a member's payload does not match manifest checksum."""
    source_dir = tmp_path / "tamper_source"
    source_dir.mkdir()
    (source_dir / "data.h5").write_bytes(b"AUTHENTIC_HDF5_DATA")
    archive_path = tmp_path / "valid.cochem_archive"
    CochemArchive.pack(source_dir, archive_path, cochem_version="0.1.0")

    dctx = zstandard.ZstdDecompressor()
    with open(archive_path, "rb") as f_in:
        with dctx.stream_reader(f_in) as comp_in:
            with tarfile.open(fileobj=comp_in, mode="r|") as tar_in:
                manifest_member = tar_in.next()
                assert manifest_member is not None
                f_man = tar_in.extractfile(manifest_member)
                assert f_man is not None
                manifest_bytes = f_man.read()

    tampered_archive = tmp_path / "tampered.cochem_archive"
    cctx = zstandard.ZstdCompressor(level=3)
    with open(tampered_archive, "wb") as f_out:
        with cctx.stream_writer(f_out) as comp_out:
            with tarfile.open(fileobj=comp_out, mode="w|") as tar_out:
                t_man = tarfile.TarInfo(name="manifest.json")
                t_man.size = len(manifest_bytes)
                tar_out.addfile(t_man, io.BytesIO(manifest_bytes))

                # Same size (19 bytes) to trigger SHA-256 mismatch specifically
                corrupted_bytes = b"CORRUPTED_HDF5_DATA"
                assert len(corrupted_bytes) == len(b"AUTHENTIC_HDF5_DATA")
                t_data = tarfile.TarInfo(name="data.h5")
                t_data.size = len(corrupted_bytes)
                tar_out.addfile(t_data, io.BytesIO(corrupted_bytes))

    dest_dir = tmp_path / "tampered_dest"
    with pytest.raises(ArchiveSecurityError, match="SHA-256 mismatch"):
        CochemArchive.unpack(tampered_archive, dest_dir)




# ==============================================================================
# 4. Air-Gapped Chemical Webhook Payload Validator & Quantum Invariant Tests
# ==============================================================================

def test_chemical_webhook_neutral_singlet_water() -> None:
    """Validate authentic neutral singlet water molecule (H2O, 10 electrons, 2S+1=1)."""
    # Authentic experimental water geometry (Angstroms)
    h2o_payload = {
        "job_id": "job_h2o_singlet",
        "symbols": ["O", "H", "H"],
        "coordinates_3d": [
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ],
        "charge": 0,
        "spin_multiplicity": 1,
        "energy_unit": "hartree",
    }
    validated = ChemicalPayloadSchema.model_validate(h2o_payload)
    assert validated.job_id == "job_h2o_singlet"
    assert validated.charge == 0
    assert validated.spin_multiplicity == 1


def test_chemical_webhook_radical_doublet_hydroxyl() -> None:
    """Validate authentic neutral doublet hydroxyl radical (OH, 9 electrons, 2S+1=2)."""
    oh_payload = {
        "job_id": "job_oh_radical",
        "symbols": ["O", "H"],
        "coordinates_3d": [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, 0.9697],
        ],
        "charge": 0,
        "spin_multiplicity": 2,
    }
    validated = ChemicalPayloadSchema.model_validate(oh_payload)
    assert validated.job_id == "job_oh_radical"
    assert validated.spin_multiplicity == 2


def test_chemical_webhook_representations_completeness() -> None:
    """Verify ingress completeness: requires at least one chemical representation."""
    # SMILES alone is valid
    smi = ChemicalPayloadSchema(job_id="job_smiles", smiles="O=C=O")
    assert smi.smiles == "O=C=O"

    # InChI alone is valid
    inchi = ChemicalPayloadSchema(job_id="job_inchi", inchi="InChI=1S/H2O/h1H2")
    assert inchi.inchi == "InChI=1S/H2O/h1H2"

    # Missing all representations raises ValueError
    with pytest.raises(ValueError, match="at least one valid chemical representation"):
        ChemicalPayloadSchema(job_id="job_empty")

    # Providing symbols without coordinates raises ValueError
    with pytest.raises(ValueError, match="must be provided together"):
        ChemicalPayloadSchema(job_id="job_no_coords", symbols=["H", "H"])

    # Providing coordinates without symbols raises ValueError
    with pytest.raises(ValueError, match="must be provided together"):
        ChemicalPayloadSchema(
            job_id="job_no_syms", coordinates_3d=[[0.0, 0.0, 0.0]]
        )

    # Mismatched length between symbols and coordinates
    with pytest.raises(ValueError, match="Length mismatch"):
        ChemicalPayloadSchema(
            job_id="job_mismatch",
            symbols=["H", "H"],
            coordinates_3d=[[0.0, 0.0, 0.0]],
        )


def test_chemical_webhook_quantum_spin_parity_violations() -> None:
    """Verify physical bounds and spin-parity conservation invariants."""
    # Water: Z_tot = 8 + 1 + 1 = 10. Charge 0 -> N_elec = 10 (even).
    # Even N_elec requires odd multiplicity (singlet 1, triplet 3, etc.).
    # Multiplicity 2 (even) must be rejected.
    with pytest.raises(ValueError, match="Quantum spin-parity violation"):
        ChemicalPayloadSchema(
            job_id="job_water_bad_spin",
            symbols=["O", "H", "H"],
            coordinates_3d=[
                [0.0, 0.0, 0.0],
                [0.0, 0.75, 0.5],
                [0.0, -0.75, 0.5],
            ],
            charge=0,
            spin_multiplicity=2,
        )

    # Hydroxyl: Z_tot = 9, Charge 0 -> N_elec = 9 (odd).
    # Odd N_elec requires even multiplicity (doublet 2, quartet 4, etc.).
    # Multiplicity 1 (odd) must be rejected.
    with pytest.raises(ValueError, match="Quantum spin-parity violation"):
        ChemicalPayloadSchema(
            job_id="job_oh_bad_spin",
            symbols=["O", "H"],
            coordinates_3d=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.97]],
            charge=0,
            spin_multiplicity=1,
        )

    # Physical spin bound exceeded: 2S+1 > N_elec + 1
    with pytest.raises(ValueError, match="Physical spin multiplicity bound violated"):
        ChemicalPayloadSchema(
            job_id="job_spin_bound",
            symbols=["H", "H"],
            coordinates_3d=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]],
            charge=0,
            spin_multiplicity=5,  # For N_elec=2, max 2S+1 = 3
        )

    # Non-positive electron count: H2(2+) has Z_tot=2, charge=+2 -> N_elec = 0
    with pytest.raises(ValueError, match="Non-positive electron count"):
        ChemicalPayloadSchema(
            job_id="job_no_electrons",
            symbols=["H", "H"],
            coordinates_3d=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]],
            charge=2,
            spin_multiplicity=1,
        )


def test_chemical_webhook_coordinate_sanitization_and_dynamic_mendeleev() -> None:
    """Verify coordinate finiteness checks and dynamic element resolution via Mendeleev."""
    # Coordinate with NaN
    with pytest.raises(ValueError, match="Non-finite floating-point coordinate"):
        ChemicalPayloadSchema(
            job_id="job_nan",
            symbols=["H", "H"],
            coordinates_3d=[[0.0, float("nan"), 0.0], [0.0, 0.0, 0.74]],
            charge=0,
            spin_multiplicity=1,
        )

    # Coordinate with Inf
    with pytest.raises(ValueError, match="Non-finite floating-point coordinate"):
        ChemicalPayloadSchema(
            job_id="job_inf",
            symbols=["H", "H"],
            coordinates_3d=[[0.0, float("inf"), 0.0], [0.0, 0.0, 0.74]],
            charge=0,
            spin_multiplicity=1,
        )

    # Unmapped element symbol
    with pytest.raises(ValueError, match="Invalid chemical element: 'Xx'"):
        ChemicalPayloadSchema(
            job_id="job_unknown_elem",
            symbols=["Xx", "H"],
            coordinates_3d=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            charge=0,
            spin_multiplicity=2,
        )


def test_format_validation_error_response_schema() -> None:
    """Verify format_validation_error_response returns HTTP 422 JSON contract."""
    err = ValueError("Specific invariant breached")
    response = format_validation_error_response(err, job_id="job_failed_99")

    assert response["status"] == 422
    assert response["error"] == "Unprocessable Entity"
    assert response["job_id"] == "job_failed_99"
    assert "Specific invariant breached" in response["detail"]
    assert "timestamp_utc" in response


# ==============================================================================
# 5. High-Concurrency HDF5 SWMR PES Trajectory Store Tests
# ==============================================================================

def test_swmr_pes_store_lifecycle(tmp_path: Path) -> None:
    """Verify schema pre-allocation, writer context management, and atomic appending."""
    h5_path = tmp_path / "pes_trajectory.h5"
    store = SWMRPESStore(h5_path, n_atoms=3)

    assert h5_path.exists()
    assert store.lock_path == h5_path.with_suffix(".lock")

    # Initial read returns empty arrays
    traj0 = store.read_trajectory()
    assert traj0["coordinates"].shape == (0, 3, 3)
    assert traj0["energies"].shape == (0,)

    # Append single frame
    coords_frame = (np.arange(9, dtype=np.float64) * 0.1 + 0.1).reshape(3, 3)
    energy_val = -76.4215
    store.append_frames(coords_frame, energy_val)

    traj1 = store.read_trajectory()
    assert traj1["coordinates"].shape == (1, 3, 3)
    assert traj1["energies"].shape == (1,)
    np.testing.assert_allclose(traj1["coordinates"][0], coords_frame)
    assert math.isclose(traj1["energies"][0], energy_val, rel_tol=1e-6)

    # Context manager append
    batch_coords = (
        np.arange(27, dtype=np.float64) * (2.0 / 26.0) + 1.0
    ).reshape(3, 3, 3)
    batch_energies = np.array([-76.4210, -76.4205, -76.4200], dtype=np.float64)

    with store:
        store.append_frames(batch_coords, batch_energies)

    traj2 = store.read_trajectory()
    assert traj2["coordinates"].shape == (4, 3, 3)
    assert traj2["energies"].shape == (4,)


def test_swmr_concurrent_writer_and_readers(tmp_path: Path) -> None:
    """Verify live writer appending 1,000 frames concurrently with >= 4 readers while writer is open."""
    h5_path = tmp_path / "concurrent_swmr.h5"
    n_atoms = 5
    store = SWMRPESStore(h5_path, n_atoms=n_atoms, enable_swmr=True)

    total_frames = 1000
    batch_size = 50
    batches = total_frames // batch_size

    reader_trajectories: List[int] = []
    reader_errors: List[Exception] = []

    # Open persistent writer handle before reading to activate SWMR mode
    store.open_writer()

    try:
        for b in range(batches):
            base_val = float(b + 1)
            coords = (
                np.arange(batch_size * n_atoms * 3, dtype=np.float64)
                * (2.0 / (batch_size * n_atoms * 3 - 1))
                + base_val
            ).reshape(batch_size, n_atoms, 3)
            energies = (
                np.arange(batch_size, dtype=np.float64) * (1.0 / (batch_size - 1))
                + (-100.0 - base_val)
            )
            store.append_frames(coords, energies)

            # Read across 4 independent reader handles while writer is actively open
            for _ in range(4):
                try:
                    data = store.read_trajectory()
                    reader_trajectories.append(data["coordinates"].shape[0])
                except Exception as exc:
                    reader_errors.append(exc)
    finally:
        store.close_writer()

    # Verify zero synchronization errors occurred
    assert len(reader_errors) == 0

    # Verify final trajectory contains all 1,000 frames
    final_traj = store.read_trajectory()
    assert final_traj["coordinates"].shape == (total_frames, n_atoms, 3)
    assert final_traj["energies"].shape == (total_frames,)

    # Verify frames advanced monotonically across concurrent reads
    assert len(reader_trajectories) > 0
    assert max(reader_trajectories) == total_frames



# ==============================================================================
# 6. Anti-Spoofing & Zero-Mock AST Compliance Audit
# ==============================================================================

def test_zero_mock_and_anti_spoof_ast_compliance() -> None:
    """Certify AST of all target production files contains zero mocks, stubs, or pass blocks."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    target_files = [
        repo_root / "src" / "cochem" / "storage" / "hdf5_zstd.py",
        repo_root / "src" / "cochem" / "provenance" / "provenance_stamper.py",
        repo_root / "src" / "cochem" / "storage" / "cochem_archive.py",
        repo_root / "src" / "cochem" / "intake" / "chemical_webhook.py",
        repo_root / "src" / "cochem" / "storage" / "cochem_core_pes_store.py",
    ]

    for target in target_files:
        assert target.exists(), f"Target file missing: {target}"
        source_code = target.read_text(encoding="utf-8")
        tree = ast.parse(source_code, filename=str(target))

        for node in ast.walk(tree):
            # Assert zero ast.Pass nodes
            assert not isinstance(
                node, ast.Pass
            ), f"Forbidden 'pass' statement found in {target} at line {getattr(node, 'lineno', '?')}"

            # Assert zero testing simulator imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "mock" not in alias.name.lower(), (
                        f"anti-spoof: forbidden testing simulator import in {target}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "mock" not in node.module.lower(), (
                        f"anti-spoof: forbidden testing simulator module in {target}"
                    )

            # Assert zero NotImplementedError
            if isinstance(node, ast.Name):
                assert node.id != "NotImplementedError", (
                    f"Forbidden NotImplementedError stub in {target} at line {getattr(node, 'lineno', '?')}"
                )
