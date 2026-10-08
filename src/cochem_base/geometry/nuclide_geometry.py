"""Preserve nuclear identity separately from electronic element symbols.

Electronic engines consume canonical element symbols. Nuclear mass operations
and immutable module handoffs retain the ordered nuclide assignment instead.
No mass is inferred from the integer mass number: Mendeleev supplies all masses.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence

from cochem_base.physics.isotopes import get_atomic_mass, normalize_nuclide_symbol, ZeroMassSystemError
from cochem_base.physics.nuclide_resolver import InvalidNuclideSymbolError, get_element
from cochem_base.spectroscopy.isotopologue import get_nuclide_mass


PRINCIPAL_MASS_CONVENTION = "explicit_isotope_mass_else_principal_isotope_mass"
HISTORICAL_AVERAGE_MASS_CONVENTION = "explicit_isotope_mass_else_standard_atomic_weight"


@dataclass(frozen=True)
class NuclearIdentity:
    elements: tuple[str, ...]
    nuclides: tuple[str, ...]
    mass_numbers: tuple[int | None, ...]
    masses_u: tuple[float, ...]

    @property
    def metadata(self) -> dict[str, Any]:
        return {"nuclides": list(self.nuclides), "mass_numbers": list(self.mass_numbers),
                "masses_u": list(self.masses_u), "mass_source": "dynamic_mendeleev",
                "mass_convention": PRINCIPAL_MASS_CONVENTION}


@dataclass(frozen=True)
class GeometryIdentity(NuclearIdentity):
    coordinates_angstrom: tuple[tuple[float, float, float], ...]


def resolve_nuclear_identity(tokens: Sequence[str], *, allow_ghosts: bool = False) -> NuclearIdentity:
    """Validate real nuclei and normalize aliases into prefix isotope notation.

    A known isotope with a measured mass remains valid even when its natural
    abundance is absent (for example tritium). Ghost centers are excluded from
    general geometry ingestion; specialised counterpoise decks handle them.
    """
    return _resolve_nuclear_identity(tokens, allow_ghosts=allow_ghosts)


def _resolve_nuclear_identity(tokens: Sequence[str], *, historical_average: bool = False, allow_ghosts: bool = False) -> NuclearIdentity:
    if isinstance(tokens, (str, bytes)) or not tokens:
        raise ValueError("An ordered nonempty sequence of nuclear labels is required")
    elements, nuclides, numbers, masses = [], [], [], []
    for token in tokens:
        normalized = normalize_nuclide_symbol(token)
        if normalized.is_ghost:
            if not allow_ghosts:
                raise ValueError("Ghost basis centers require an explicit counterpoise geometry adapter")
            elements.append("Gh")
            nuclides.append(normalized.canonical_symbol)
            numbers.append(None)
            masses.append(0.0)
            continue
        symbol, number = normalized.canonical_symbol, normalized.mass_number
        if number is not None and number <= 0:
            raise ValueError("Isotope mass number must be a positive integer")
        try:
            element = get_element(symbol)
        except InvalidNuclideSymbolError as error:
            raise ValueError(f"A real element symbol is required for each nucleus: {token}") from error
        if int(element.atomic_number) < 1:
            raise ValueError("A real element symbol is required for each nucleus")
        mass = get_atomic_mass(symbol) if historical_average and number is None else get_nuclide_mass(symbol, number)
        if not math.isfinite(mass) or mass <= 0:
            raise ValueError(f"Nonphysical nuclear mass for {token}")
        elements.append(symbol)
        nuclides.append(symbol if number is None else f"{number}{symbol}")
        numbers.append(number)
        masses.append(mass)
    if not any(mass > 0 for mass in masses):
        raise ZeroMassSystemError("All atoms are ghost centers; center of mass undefined.")
    return NuclearIdentity(tuple(elements), tuple(nuclides), tuple(numbers), tuple(masses))


def validate_nuclear_identity_metadata(
    tokens: Sequence[str], metadata: Any, *, allow_historical: bool = False,
) -> dict[str, Any]:
    """Validate recorded masses against their declared dynamic convention.

    Historical averaged-mass results may be imported as historical records. The
    return value preserves their declared convention and original mass values;
    it must not serve as the principal-isotope authority for a new calculation.
    Explicit isotope numbers always require a real exact database mass.
    """
    historical = isinstance(metadata, dict) and allow_historical and metadata.get("mass_convention") == HISTORICAL_AVERAGE_MASS_CONVENTION
    identity = _resolve_nuclear_identity(tokens, historical_average=historical)
    expected = identity.metadata
    if historical:
        expected = dict(expected, mass_convention=HISTORICAL_AVERAGE_MASS_CONVENTION,
                        masses_u=list(identity.masses_u))
    if not isinstance(metadata, dict) or metadata != expected:
        raise ValueError("Recorded nuclear identity disagrees with its isotope assignments or declared mass convention")
    return dict(metadata)


def parse_geometry_identity(text: str) -> GeometryIdentity:
    """Read one XYZ frame or coordinate block with complete nuclear identities."""
    # A Windows UTF-8 signature is encoding metadata, not an atom/count token.
    # Only the parsing view changes; callers retain their original bytes/hash.
    lines = text.removeprefix("\ufeff").strip().splitlines()
    if not lines:
        raise ValueError("Geometry cannot be empty")
    expected = None
    if lines[0].strip().isdigit():
        expected = int(lines[0])
        if len(lines) < 3:
            raise ValueError("Incomplete XYZ frame")
        lines = lines[2:]
    labels, coordinates = [], []
    for line in lines:
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(f"Invalid XYZ coordinate line: {line}")
        xyz = tuple(float(value) for value in fields[1:])
        if not all(math.isfinite(value) for value in xyz):
            raise ValueError("Geometry coordinates must be finite")
        labels.append(fields[0])
        coordinates.append(xyz)
    if not labels or expected is not None and len(labels) != expected:
        raise ValueError("XYZ atom count does not match its coordinates")
    identity = resolve_nuclear_identity(labels)
    return GeometryIdentity(identity.elements, identity.nuclides, identity.mass_numbers,
                            identity.masses_u, tuple(coordinates))


def rdkit_geometry_xyz(molecule: Any, *, comment: str = "CoChem RDKit geometry with nuclear assignments") -> str:
    """Serialize a real RDKit conformer without dropping SMILES isotope labels."""
    if "\n" in comment or "\r" in comment:
        raise ValueError("XYZ comment must be one line")
    conformer = molecule.GetConformer()
    labels = [f"{atom.GetIsotope()}{atom.GetSymbol()}" if atom.GetIsotope() else atom.GetSymbol()
              for atom in molecule.GetAtoms()]
    identity = resolve_nuclear_identity(labels)
    lines = [str(len(labels)), comment]
    for index, label in enumerate(identity.nuclides):
        position = conformer.GetAtomPosition(index)
        xyz = (float(position.x), float(position.y), float(position.z))
        if not all(math.isfinite(value) for value in xyz):
            raise ValueError("RDKit coordinates must be finite")
        lines.append(label + " " + " ".join(format(value, ".17g") for value in xyz))
    return "\n".join(lines) + "\n"
