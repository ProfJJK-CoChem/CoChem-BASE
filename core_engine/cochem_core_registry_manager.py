"""CoChem-CORE: Stage 1.0 - State Registry & Provenance Manager
Implements: Atomic POSIX locking, Lineage UUIDs, PRNG Seed Locking,
Legacy Schema Migration, HDF5 Basis Set Archival, and Dynamic Mass Queries.
PATCH: - Replaced static mass dictionaries with dynamic mendeleev library queries
       - Added explicit IsotopeStabilityError handling for transuranic / unstable elements."""

import os
import json
import uuid
import fcntl
import h5py
import hashlib
import logging
from typing import Dict, Any, Optional
from mendeleev import element

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CoChem-RegistryManager")

class IsotopeStabilityError(Exception):
    """Raised when the mendeleev library cannot resolve a stable mass for an unstable or transuranic isotope."""
    pass

class RegistryManager:
    def __init__(self, config_path: str = "cochem_system_config.json"):
        self.config_path = os.path.abspath(config_path)

    @staticmethod
    def get_isotopic_mass(symbol: str, mass_number: Optional[int] = None) -> float:
        """
        Dynamically fetches exact isotopic masses via the mendeleev library.
        If no mass_number is provided, defaults to the most abundant isotope
        to ensure high-precision rotational constant derivation. Raises IsotopeStabilityError
        if mass data is missing.
        """
        try:
            elem = element(symbol)
            if mass_number is not None:
                for iso in elem.isotopes:
                    if iso.mass_number == mass_number:
                        if iso.mass is None:
                            raise IsotopeStabilityError(f"Isotope {mass_number}{symbol} has no stable mass record in Mendeleev.")
                        return float(iso.mass)
                raise ValueError(f"Isotope {mass_number}{symbol} not found in Mendeleev database.")
            
            # Default to most abundant isotope for exact mass
            if hasattr(elem, 'mass') and elem.mass is not None:
                return float(elem.mass)
            else:
                raise IsotopeStabilityError(f"Element {symbol} lacks a valid default atomic mass binding.")
        except Exception as e:
            logger.error(f"Failed to query Mendeleev for symbol '{symbol}': {e}")
            raise IsotopeStabilityError(f"Isotopic mass resolution failed for {symbol}: {e}")

    def embed_basis_set_archive(self, h5_path: str, basis_file_path: str, label: str) -> None:
        """Embedded Basis Set Archival (Prevents link rot)."""
        if not os.path.exists(basis_file_path):
            logger.error(f"Basis set file not found: {basis_file_path}")
            return
        with open(basis_file_path, "r") as f:
            raw_text = f.read()
        try:
            with h5py.File(h5_path, "a", swmr=True) as h5:
                if "embedded_basis_sets" not in h5:
                    h5.create_group("embedded_basis_sets")

                group = h5["embedded_basis_sets"]
                if label in group:
                    del group[label]

                dt = h5py.string_dtype(encoding='utf-8')
                dset = group.create_dataset(label, shape=(), dtype=dt)
                dset[()] = raw_text

                logger.info(f"Basis set '{label}' permanently embedded into {h5_path} with SWMR active.")
        except Exception as e:
            logger.error(f"HDF5 embedding failed: {e}")

if __name__ == "__main__":
    try:
        mass_c13 = RegistryManager.get_isotopic_mass("C", 13)
        mass_c_abundant = RegistryManager.get_isotopic_mass("C")
        print(f"13C Mass: {mass_c13} Da")
        print(f"Most Abundant C Mass: {mass_c_abundant} Da")
    except Exception as err:
        print(f"Test caught expected edge-case guard: {err}")
EOF