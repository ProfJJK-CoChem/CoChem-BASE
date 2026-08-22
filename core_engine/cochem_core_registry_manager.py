#!/usr/bin/env python3
"""CoChem-CORE: Stage 1.0 - State Registry & Provenance Manager.

Implements: Atomic File Locking, Lineage UUIDs, PRNG Seed Locking,
Legacy Schema Migration, HDF5 Basis Set Archival, and Dynamic Mass Queries.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, Generator, List, Optional, Union
import uuid

from filelock import FileLock
import h5py
from pydantic import BaseModel

try:
    from mendeleev import element
except ImportError:
    element = None

try:
    from qcelemental import periodictable as pt
except ImportError:
    pt = None

from cochem_base.config_loader import get_artifact_dir, resolve_config_path, resolve_mapped_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CoChem-RegistryManager")


class RegistryError(Exception):
    """Base exception for all registry operations."""


class RegistryLockError(RegistryError):
    """Raised when file locking fails."""


class RecordNotFoundError(RegistryError):
    """Raised when a queried job or profile is not found in the registry."""


class BasisSetNotFoundError(RegistryError):
    """Raised when an archived basis set cannot be located."""


class SchemaMigrationError(RegistryError):
    """Raised when schema migration encounters an unrecoverable failure."""


class IsotopeStabilityError(RegistryError):
    """Raised when isotopic mass resolution fails or mass record is missing."""


class RegistryManager:
    """Consolidated state registry manager using HDF5 and atomic file locks."""

    SCHEMA_VERSION = "1.0.0"

    def __init__(self, config_path: Optional[str] = None, registry_path: Optional[str] = None) -> None:
        if config_path:
            self.config_path = str(resolve_config_path(Path(config_path)))
        else:
            self.config_path = str(resolve_config_path())

        if registry_path:
            self.registry_path = str(resolve_mapped_path(registry_path, get_artifact_dir() / "Registry"))
        else:
            self.registry_path = str(get_artifact_dir() / "Registry" / "cochem_registry.h5")

        self.lock_path = self.registry_path + ".lock"
        self._ensure_registry_exists()

    def _ensure_registry_exists(self) -> None:
        """Ensure the HDF5 registry file and required groups exist, with atomic locking."""
        try:
            os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
            with FileLock(self.lock_path, timeout=10):
                if not os.path.exists(self.registry_path):
                    with h5py.File(self.registry_path, "w") as h5:
                        h5.attrs["created"] = datetime.now(timezone.utc).isoformat()
                        h5.attrs["version"] = self.SCHEMA_VERSION
                        h5.create_group("jobs")
                        h5.create_group("hardware_profiles")
                        h5.create_group("basis_sets")
                        h5.create_group("embedded_basis_sets")
                        h5.create_group("provenance")
                        h5.create_group("seeds")
                        h5.create_group("metadata")
                    logger.info(f"Created new registry file: {self.registry_path}")
                else:
                    with h5py.File(self.registry_path, "a") as h5:
                        if "version" not in h5.attrs:
                            h5.attrs["version"] = self.SCHEMA_VERSION
                        for grp in ["jobs", "hardware_profiles", "basis_sets", "embedded_basis_sets", "provenance", "seeds", "metadata"]:
                            if grp not in h5:
                                h5.create_group(grp)
        except Exception as e:
            logger.error(f"Failed to initialize registry: {e}")
            raise RuntimeError(f"Registry initialization failed: {e}") from e

    @contextmanager
    def transaction(self, mode: str = "a") -> Generator[h5py.File, None, None]:
        """Provides an atomic transaction over the HDF5 registry."""
        with FileLock(self.lock_path, timeout=10):
            with h5py.File(self.registry_path, mode) as h5:
                yield h5

    def get_registry_stats(self) -> Dict[str, Any]:
        """Returns statistics on active registry record groups."""
        with self.transaction("r") as h5:
            jobs_c = len(h5["jobs"]) if "jobs" in h5 else 0
            hw_c = len(h5["hardware_profiles"]) if "hardware_profiles" in h5 else 0
            prov_c = len(h5["provenance"]) if "provenance" in h5 else 0
            basis_c = len(h5["embedded_basis_sets"]) if "embedded_basis_sets" in h5 else (len(h5["basis_sets"]) if "basis_sets" in h5 else 0)
            seeds_c = len(h5["seeds"]) if "seeds" in h5 else 0
            ver = h5.attrs.get("version", self.SCHEMA_VERSION)
            if isinstance(ver, bytes):
                ver = ver.decode("utf-8")
            return {
                "jobs_count": jobs_c,
                "hardware_profiles_count": hw_c,
                "provenance_count": prov_c,
                "basis_sets_count": basis_c,
                "seeds_count": seeds_c,
                "version": str(ver),
            }

    @staticmethod
    def get_isotopic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
        """Dynamically fetches exact isotopic masses via mendeleev or qcelemental."""
        if symbol is None or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Chemical element symbol cannot be empty or None.")

        clean_sym = symbol.strip()
        formatted_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym

        if mass_number is not None and not isinstance(mass_number, int):
            raise ValueError("Mass number must be an integer.")

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception as e:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        raise IsotopeStabilityError(f"Element {clean_sym} not found in Mendeleev.") from e

                if mass_number is not None:
                    for iso in elem.isotopes:
                        if iso.mass_number == mass_number:
                            if iso.mass is None:
                                raise IsotopeStabilityError(f"Isotope {mass_number}{clean_sym} has no stable mass record in Mendeleev.")
                            return float(iso.mass)
                    raise ValueError(f"Isotope {mass_number}{clean_sym} not found in Mendeleev database.")

                if hasattr(elem, "mass") and elem.mass is not None:
                    return float(elem.mass)
                raise IsotopeStabilityError(f"Element {clean_sym} lacks a valid default atomic mass binding.")
            except (ValueError, IsotopeStabilityError):
                raise
            except Exception as e:
                logger.error(f"Failed to query Mendeleev for symbol '{clean_sym}': {e}")
                raise IsotopeStabilityError(f"Isotopic mass resolution failed for {clean_sym}: {e}") from e

        if pt is not None:
            try:
                if mass_number is not None:
                    target = f"{formatted_sym}{mass_number}"
                    return float(pt.to_mass(target))
                return float(pt.to_mass(formatted_sym))
            except Exception as e:
                logger.error(f"Failed to query QCElemental for symbol '{clean_sym}': {e}")
                raise IsotopeStabilityError(f"Isotopic mass resolution failed for {clean_sym}: {e}") from e

        raise IsotopeStabilityError("Neither mendeleev nor qcelemental library is available for isotopic mass resolution.")

    @staticmethod
    def get_all_isotopes(symbol: str) -> List[Dict[str, Any]]:
        """Returns all isotopic variants for a given chemical element symbol."""
        if symbol is None or not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Chemical element symbol cannot be empty or None.")

        clean_sym = symbol.strip()
        formatted_sym = clean_sym.capitalize() if len(clean_sym) <= 2 else clean_sym

        if element is not None:
            try:
                try:
                    elem = element(formatted_sym)
                except Exception as e:
                    try:
                        elem = element(clean_sym)
                    except Exception:
                        raise IsotopeStabilityError(f"Element {clean_sym} not found in Mendeleev.") from e

                isotopes = []
                for iso in elem.isotopes:
                    isotopes.append({
                        "mass_number": int(iso.mass_number),
                        "mass": float(iso.mass) if iso.mass is not None else None,
                        "abundance": float(iso.abundance) if getattr(iso, "abundance", None) is not None else None,
                    })
                return isotopes
            except IsotopeStabilityError:
                raise
            except Exception as e:
                raise IsotopeStabilityError(f"Failed to fetch isotopes for {clean_sym}: {e}") from e

        raise IsotopeStabilityError("Mendeleev is not available to list isotopes.")


    def register_job(self, job_id: str, job_data: Union[Dict[str, Any], BaseModel]) -> None:
        """Registers a calculation job record in the HDF5 registry."""
        if not job_id or not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("Job ID must be a non-empty string.")

        payload = job_data.model_dump() if isinstance(job_data, BaseModel) else dict(job_data)
        if "registered_at" not in payload:
            payload["registered_at"] = datetime.now(timezone.utc).isoformat()

        json_str = json.dumps(payload)
        with self.transaction("a") as h5:
            jobs_grp = h5["jobs"]
            if job_id in jobs_grp:
                del jobs_grp[job_id]
            dset = jobs_grp.create_dataset(job_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8"))
            dset.attrs["updated_at"] = datetime.now(timezone.utc).isoformat()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a registered job record, or None if not found."""
        with self.transaction("r") as h5:
            if "jobs" not in h5 or job_id not in h5["jobs"]:
                return None
            val = h5["jobs"][job_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return json.loads(text)

    def update_job_status(self, job_id: str, status: str, **kwargs: Any) -> None:
        """Updates the status and additional fields of an existing job record."""
        with self.transaction("a") as h5:
            jobs_grp = h5["jobs"]
            if job_id not in jobs_grp:
                raise ValueError("Cannot update status for non-existent job")
            val = jobs_grp[job_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            rec = json.loads(text)
            rec["status"] = status
            rec.update(kwargs)
            rec["updated_at"] = datetime.now(timezone.utc).isoformat()
            del jobs_grp[job_id]
            jobs_grp.create_dataset(job_id, data=json.dumps(rec), dtype=h5py.string_dtype(encoding="utf-8"))

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Returns all registered jobs with job_id included."""
        results = []
        with self.transaction("r") as h5:
            if "jobs" in h5:
                for k in h5["jobs"].keys():
                    val = h5["jobs"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    data["job_id"] = k
                    results.append(data)
        return results

    def delete_job(self, job_id: str) -> bool:
        """Deletes a job from the registry."""
        with self.transaction("a") as h5:
            if "jobs" in h5 and job_id in h5["jobs"]:
                del h5["jobs"][job_id]
                return True
            return False

    def register_hardware_profile(
        self, profile_id: str, profile_data: Union[Dict[str, Any], BaseModel]
    ) -> None:
        """Registers a host/node hardware configuration profile."""
        if not profile_id or not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Profile ID must be a non-empty string.")

        payload = profile_data.model_dump() if isinstance(profile_data, BaseModel) else dict(profile_data)
        payload["registered_at"] = datetime.now(timezone.utc).isoformat()
        json_str = json.dumps(payload)

        with self.transaction("a") as h5:
            hw_grp = h5["hardware_profiles"]
            if profile_id in hw_grp:
                del hw_grp[profile_id]
            hw_grp.create_dataset(profile_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8"))

    def get_hardware_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a registered hardware profile by ID."""
        with self.transaction("r") as h5:
            if "hardware_profiles" not in h5 or profile_id not in h5["hardware_profiles"]:
                return None
            val = h5["hardware_profiles"][profile_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return json.loads(text)

    def get_all_hardware_profiles(self) -> List[Dict[str, Any]]:
        """Returns all hardware profiles."""
        results = []
        with self.transaction("r") as h5:
            if "hardware_profiles" in h5:
                for k in h5["hardware_profiles"].keys():
                    val = h5["hardware_profiles"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    data["profile_id"] = k
                    results.append(data)
        return results

    def delete_hardware_profile(self, profile_id: str) -> bool:
        """Deletes a hardware profile from the registry."""
        with self.transaction("a") as h5:
            if "hardware_profiles" in h5 and profile_id in h5["hardware_profiles"]:
                del h5["hardware_profiles"][profile_id]
                return True
            return False

    def add_provenance_record(self, record_id: str, record_data: Dict[str, Any]) -> str:
        """Adds a cryptographic/workflow provenance record and returns a unique lineage UUID."""
        if not record_id or not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("Record ID must be a non-empty string.")

        lineage_uuid = f"lin_{uuid.uuid4().hex}"
        payload = dict(record_data)
        payload["record_id"] = record_id
        payload["lineage_uuid"] = lineage_uuid
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

        json_str = json.dumps(payload)
        with self.transaction("a") as h5:
            prov_grp = h5["provenance"]
            if record_id in prov_grp:
                del prov_grp[record_id]
            prov_grp.create_dataset(record_id, data=json_str, dtype=h5py.string_dtype(encoding="utf-8"))

        return lineage_uuid

    def get_provenance_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a provenance record by ID."""
        with self.transaction("r") as h5:
            if "provenance" not in h5 or record_id not in h5["provenance"]:
                return None
            val = h5["provenance"][record_id][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return json.loads(text)

    def get_lineage_chain(self, leaf_record_id: str) -> List[Dict[str, Any]]:
        """Traces the backward DAG lineage chain from leaf to root."""
        chain = []
        curr_id = leaf_record_id
        all_prov = {p["lineage_uuid"]: p for p in self.get_all_provenance_records()}
        rec_by_id = {p["record_id"]: p for p in all_prov.values()}

        curr = rec_by_id.get(curr_id)
        while curr is not None:
            chain.append(curr)
            parent_uuid = curr.get("parent_uuid")
            if not parent_uuid or parent_uuid not in all_prov:
                break
            curr = all_prov.get(parent_uuid)

        return chain

    def get_all_provenance_records(self) -> List[Dict[str, Any]]:
        """Returns all provenance records."""
        results = []
        with self.transaction("r") as h5:
            if "provenance" in h5:
                for k in h5["provenance"].keys():
                    val = h5["provenance"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    data = json.loads(text)
                    results.append(data)
        return results

    def delete_provenance_record(self, record_id: str) -> bool:
        """Deletes a provenance record."""
        with self.transaction("a") as h5:
            if "provenance" in h5 and record_id in h5["provenance"]:
                del h5["provenance"][record_id]
                return True
            return False

    def lock_prng_seed(
        self, seed: int, scope: str = "global", metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Locks a pseudorandom number generator seed into the registry."""
        if not isinstance(seed, int):
            raise ValueError("PRNG seed must be an integer.")

        payload = {
            "seed": seed,
            "scope": scope,
            "metadata": metadata or {},
            "locked_at": datetime.now(timezone.utc).isoformat(),
        }

        with self.transaction("a") as h5:
            seeds_grp = h5["seeds"]
            if scope in seeds_grp:
                del seeds_grp[scope]
            seeds_grp.create_dataset(scope, data=json.dumps(payload), dtype=h5py.string_dtype(encoding="utf-8"))

        return seed

    def get_locked_seed(self, scope: str = "global") -> Optional[int]:
        """Retrieves a locked PRNG seed for a given scope."""
        with self.transaction("r") as h5:
            if "seeds" not in h5 or scope not in h5["seeds"]:
                return None
            val = h5["seeds"][scope][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return json.loads(text).get("seed")

    def verify_prng_seed(self, seed: int, scope: str = "global") -> bool:
        """Verifies if an active seed matches the registered locked seed for a scope."""
        locked = self.get_locked_seed(scope)
        return locked is not None and locked == seed

    def list_locked_seeds(self) -> Dict[str, int]:
        """Returns all locked seeds mapped by scope."""
        res = {}
        with self.transaction("r") as h5:
            if "seeds" in h5:
                for k in h5["seeds"].keys():
                    val = h5["seeds"][k][()]
                    text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                    res[k] = json.loads(text).get("seed")
        return res

    def embed_basis_set_archive(
        self, h5_path: str, basis_file_path: str, label: str, is_content: bool = False
    ) -> None:
        """Embeds full basis set text into the HDF5 archive to prevent link rot."""
        if not label or not isinstance(label, str) or not label.strip():
            raise ValueError("Basis set label must be a non-empty string.")

        clean_label = label.strip()

        if is_content:
            raw_text = basis_file_path
        else:
            p = Path(basis_file_path)
            if not p.is_file():
                raise FileNotFoundError(f"Basis set file not found: {p}")
            raw_text = p.read_text(encoding="utf-8")

        mapped_h5 = Path(h5_path)
        with FileLock(str(mapped_h5) + ".lock", timeout=10):
            with h5py.File(mapped_h5, "a") as h5:
                if "embedded_basis_sets" not in h5:
                    h5.create_group("embedded_basis_sets")
                grp = h5["embedded_basis_sets"]
                if clean_label in grp:
                    del grp[clean_label]
                grp.create_dataset(clean_label, data=raw_text, dtype=h5py.string_dtype(encoding="utf-8"))

    def has_embedded_basis_set(self, label: str) -> bool:
        """Checks if a basis set label exists in the registry."""
        with self.transaction("r") as h5:
            return "embedded_basis_sets" in h5 and label in h5["embedded_basis_sets"]

    def get_embedded_basis_set(self, label: str) -> str:
        """Retrieves embedded basis set content."""
        with self.transaction("r") as h5:
            if "embedded_basis_sets" not in h5 or label not in h5["embedded_basis_sets"]:
                raise BasisSetNotFoundError(f"Basis set '{label}' not found in registry.")
            val = h5["embedded_basis_sets"][label][()]
            return val.decode("utf-8") if isinstance(val, bytes) else str(val)

    def list_embedded_basis_sets(self) -> List[str]:
        """Lists all embedded basis set labels."""
        with self.transaction("r") as h5:
            if "embedded_basis_sets" in h5:
                return list(h5["embedded_basis_sets"].keys())
            return []

    def delete_embedded_basis_set(self, label: str) -> bool:
        """Deletes an embedded basis set."""
        with self.transaction("a") as h5:
            if "embedded_basis_sets" in h5 and label in h5["embedded_basis_sets"]:
                del h5["embedded_basis_sets"][label]
                return True
            return False

    def migrate_legacy_schema(self) -> Dict[str, Any]:
        """Upgrades legacy HDF5 schema files to 1.0.0."""
        with self.transaction("a") as h5:
            prev_ver = h5.attrs.get("version", "0.1")
            if isinstance(prev_ver, bytes):
                prev_ver = prev_ver.decode("utf-8")

            h5.attrs["version"] = self.SCHEMA_VERSION
            h5.attrs["migrated_at"] = datetime.now(timezone.utc).isoformat()

            for grp in ["hardware_profiles", "basis_sets", "embedded_basis_sets", "provenance", "seeds", "metadata"]:
                if grp not in h5:
                    h5.create_group(grp)

            return {
                "previous_version": str(prev_ver),
                "current_version": self.SCHEMA_VERSION,
                "status": "migrated",
            }

    def set_metadata(self, key: str, value: Any) -> None:
        """Sets arbitrary metadata key/value into the registry."""
        with self.transaction("a") as h5:
            meta_grp = h5["metadata"]
            if key in meta_grp:
                del meta_grp[key]
            meta_grp.create_dataset(key, data=json.dumps(value), dtype=h5py.string_dtype(encoding="utf-8"))

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Retrieves arbitrary metadata value."""
        with self.transaction("r") as h5:
            if "metadata" not in h5 or key not in h5["metadata"]:
                return default
            val = h5["metadata"][key][()]
            text = val.decode("utf-8") if isinstance(val, bytes) else str(val)
            return json.loads(text)
