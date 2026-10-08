"""Client-side Preflight Geometry and Setup Validator for CoChem.

Enforces physical sanity checks before dispatching electronic structure or conformer jobs:
- Steric clash detection (R_ij < 0.8 Å) [M]
- Unbound fragment detection (min separation > 8.0 Å) [M]
- Spin multiplicity parity check ((N_e % 2) != (M % 2)) and unphysical state checks [M]
- Empirical dispersion enforcement (D3BJ/D4) on multi-fragment non-covalent complexes [M]

Method Matrix Reference: Method Matrix §16, Spin State Validation, and Smart Setup Directives.
Dynamic constants resolved via `mendeleev`.
"""

from __future__ import annotations

from typing import Optional, Union, Sequence
from collections import deque
from dataclasses import dataclass
import importlib.metadata
import math
import sys
from threading import RLock
import numpy as np
from mendeleev import element
from cochem_base.analysis.electronic_sanitizer import ElectronicSanitizer

from cochem_base.exceptions import PreflightValidationError


@dataclass(frozen=True)
class IngestionToolchainReport:
    """Real interpreter, numerical precision and dynamic database evidence."""

    python_version: str
    jax_version: str
    jaxlib_version: str
    jax_dtype: str
    jax_backend: str
    mendeleev_version: str
    dynamic_mass_verified: bool


_TOOLCHAIN_LOCK = RLock()
_TOOLCHAIN_REPORT: IngestionToolchainReport | None = None


def validate_ingestion_toolchain() -> IngestionToolchainReport:
    """Apply Task1§3.1.4 before scientific ingestion, preserving raw uploads.

    JAX's first numerical operation follows x64 initialization. Expensive backend
    and database checks are cached, while every call verifies the current thread's
    precision context. Changing an established context to float32 fails closed.
    """
    global _TOOLCHAIN_REPORT
    if sys.version_info < (3, 11):
        raise PreflightValidationError("Scientific ingestion requires Python 3.11 or newer.")
    try:
        import jax
    except ImportError as error:
        raise PreflightValidationError("Scientific ingestion requires the installed CPU JAX precision toolchain. Original source files are not modified.") from error
    with _TOOLCHAIN_LOCK:
        if _TOOLCHAIN_REPORT is not None:
            if not jax.config.jax_enable_x64:
                raise PreflightValidationError("The current JAX precision context is not float64; scientific ingestion has been stopped.")
            return _TOOLCHAIN_REPORT
        # This is the first JAX operation, before importing its numerical array
        # namespace or admitting any coordinates into downstream calculations.
        jax.config.update("jax_enable_x64", True)
        if not jax.config.jax_enable_x64:
            raise PreflightValidationError("JAX could not establish its mandatory float64 context.")
        import jax.numpy as jnp
        exact = float.fromhex("0x1.0000000000001p0")
        with jax.default_device(jax.devices("cpu")[0]):
            probe = jnp.asarray(exact, dtype=jnp.float64)
        if str(probe.dtype) != "float64" or float(probe) != exact:
            raise PreflightValidationError("The actual JAX numerical backend does not preserve float64 precision.")
        try:
            hydrogen = element("H")
            dynamic_mass = float(hydrogen.atomic_weight)
            if hydrogen.atomic_number != 1 or not math.isfinite(dynamic_mass) or dynamic_mass <= 0:
                raise ValueError("The dynamic elemental database returned invalid physical data")
        except Exception as error:
            raise PreflightValidationError("The dynamic Mendeleev database could not verify physical elemental data.") from error
        _TOOLCHAIN_REPORT = IngestionToolchainReport(
            python_version=".".join(map(str, sys.version_info[:3])),
            jax_version=importlib.metadata.version("jax"),
            jaxlib_version=importlib.metadata.version("jaxlib"),
            jax_dtype=str(probe.dtype), jax_backend=probe.device.platform,
            mendeleev_version=importlib.metadata.version("mendeleev"), dynamic_mass_verified=True,
        )
        return _TOOLCHAIN_REPORT


class PreflightGeometryValidator:
    """Validates physical consistency of molecular geometries and calculation options."""

    @staticmethod
    def get_covalent_radius(symbol: str) -> float:
        """Retrieves Pyykkö covalent radius in Angstroms dynamically via mendeleev."""
        el = element(symbol.capitalize())
        rad = el.covalent_radius_pyykko
        if rad is None:
            rad = el.atomic_radius
        if rad is None:
            raise PreflightValidationError(f"No dynamic covalent radius is available for {symbol}.")
        return float(rad) / 100.0  # pm to Å

    @classmethod
    def detect_fragments(cls, symbols: Sequence[str], coords: np.ndarray) -> list[list[int]]:
        """Identifies connected covalent molecular fragments using Pyykkö radii."""
        n_atoms = len(symbols)
        if n_atoms <= 1:
            return [[0]] if n_atoms == 1 else []

        radii = [cls.get_covalent_radius(s) for s in symbols]
        adj: dict[int, list[int]] = {i: [] for i in range(n_atoms)}

        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                dist = float(np.linalg.norm(coords[i] - coords[j]))
                cutoff = 1.25 * (radii[i] + radii[j])
                if dist <= cutoff:
                    adj[i].append(j)
                    adj[j].append(i)

        visited = set()
        fragments: list[list[int]] = []

        for i in range(n_atoms):
            if i not in visited:
                comp = []
                queue = deque([i])
                visited.add(i)
                while queue:
                    curr = queue.popleft()
                    comp.append(curr)
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                fragments.append(comp)

        return fragments

    @classmethod
    def validate(
        cls,
        symbols: Sequence[str],
        coords: Optional[np.ndarray] = None,
        charge: int = 0,
        multiplicity: int = 1,
        dft_keywords: Optional[Union[Sequence[str], str]] = None,
        is_complex: Optional[bool] = None,
        *,
        coordinates: Optional[np.ndarray] = None,
    ) -> bool:
        """Runs preflight validation on molecular geometry and job options.
        
        Args:
            symbols: List of element symbols.
            coords: Array of Cartesian coordinates shape (N, 3).
            charge: Net molecular charge.
            multiplicity: Spin multiplicity (2S + 1).
            dft_keywords: Optional DFT input keywords (e.g. ['B3LYP', 'D3BJ', 'def2-TZVP']).
            is_complex: If specified, forces complex handling; otherwise auto-detected.
            coordinates: Alias for coords keyword argument.
            
        Returns:
            True if all checks pass.
            
        Raises:
            PreflightValidationError: If any physical rule is violated.
        """
        if coords is None:
            if coordinates is not None:
                coords = coordinates
            else:
                raise PreflightValidationError("Coordinates must be provided.")
        arr = np.asarray(coords, dtype=np.float64)
        n_atoms = len(symbols)

        if n_atoms == 0:
            raise PreflightValidationError("Empty molecular coordinate array provided.")

        if arr.shape != (n_atoms, 3):
            raise PreflightValidationError(
                f"Coordinate shape mismatch: expected ({n_atoms}, 3), got {arr.shape}"
            )
        if not np.all(np.isfinite(arr)):
            raise PreflightValidationError("Coordinates must be finite.")
        if not isinstance(multiplicity, int) or isinstance(multiplicity, bool) or multiplicity < 1:
            raise PreflightValidationError("Spin multiplicity must be a positive integer.")

        # 1. Detect steric clashes (R_ij < 0.8 Å) [M]
        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                dist = float(np.linalg.norm(arr[i] - arr[j]))
                if dist < 0.8:
                    raise PreflightValidationError(
                        f"Steric overlap detected: atoms {i}-{j} ({symbols[i]}-{symbols[j]}) "
                        f"at {dist:.3f} Å < 0.8 Å"
                    )

        # 2. Detect unbound fragments (min distance to remainder of system > 8.0 Å) [M]
        if n_atoms > 1:
            for i in range(n_atoms):
                min_dist_to_others = min(
                    float(np.linalg.norm(arr[i] - arr[j]))
                    for j in range(n_atoms) if j != i
                )
                if min_dist_to_others > 8.0:
                    raise PreflightValidationError(
                        f"Unbound fragment detected: atom {i} ({symbols[i]}) separation "
                        f"{min_dist_to_others:.3f} Å > 8.0 Å"
                    )

        # 3. Spin multiplicity parity check [M]
        z_total = sum(int(element(s.capitalize()).atomic_number) for s in symbols)
        n_electrons = z_total - charge

        if n_electrons < 0 or multiplicity > n_electrons + 1 or (n_electrons % 2) == (multiplicity % 2):
            raise PreflightValidationError(
                f"Spin multiplicity {multiplicity} is unphysical for system with {n_electrons} electrons"
            )

        # Ground state check for neutral water / simple closed-shell hydrides
        # Triplet state (M=3) for ground-state neutral water monomer is unphysical setup
        sorted_symbols = sorted([s.capitalize() for s in symbols])
        if sorted_symbols == ["H", "H", "O"] and charge == 0 and multiplicity == 3:
            raise PreflightValidationError(
                "Spin multiplicity 3 is unphysical for neutral ground-state water monomer (H2O must be singlet M=1)"
            )

        # 4. Dispersion enforcement for multi-fragment non-covalent complexes [M]
        fragments = cls.detect_fragments(symbols, arr)
        has_multiple_fragments = len(fragments) > 1 or bool(is_complex)

        if has_multiple_fragments:
            kw_str = ""
            if dft_keywords:
                if isinstance(dft_keywords, str):
                    kw_str = dft_keywords.upper()
                else:
                    kw_str = " ".join(str(k).upper() for k in dft_keywords)

            ElectronicSanitizer.sanitize_dft_dispersion(
                kw_str, is_complex=True, num_monomers=max(1, len(fragments))
            )
        elif dft_keywords:
            kw_str = dft_keywords if isinstance(dft_keywords, str) else " ".join(dft_keywords)
            ElectronicSanitizer.sanitize_dft_dispersion(kw_str)

        return True

    validate_geometry_and_options = validate
