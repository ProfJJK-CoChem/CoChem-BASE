"""Comprehensive physical Zero-Mock test suite for cochem_base.io.atomic_data.

Validates:
- Full 118-element periodic table integration and IUPAC / NIST standard atomic weights.
- Isotopic mass validation against PubChem reference standards.
- Boundary condition enforcement (mass <= 0, mass > 300, unknown isotope, tolerance deviations).
- Molecular weight, monoisotopic mass, nominal mass, and mass defect calculations.
- Accurate physical isotope natural abundances (e.g. Fe-56, He-4, Li-7, B-11, Ar-40).
- Advanced chemical formula parser (simple, complex, hydrates, adducts, ionic charges).
- Direct mass and formula helpers.
- Periodic table metadata (period, group, block, category).
- Case-insensitive, symbol, name, and atomic number Z lookups.
- Backward compatibility with legacy PubChemAtomicDataValidator and validate_isotopic_mass.
- LF line endings and zero personal path leaks.
"""

from __future__ import annotations

import math
from pathlib import Path
import pytest

import cochem_base.io as io_pkg
from cochem_base.io.atomic_data import (
    ElementInfo,
    IsotopeInfo,
    PubChemAtomicDataValidator,
    calculate_molecular_weight,
    calculate_molecular_weight_from_formula,
    calculate_monoisotopic_mass,
    calculate_monoisotopic_mass_from_formula,
    get_atomic_data_validator,
    get_atomic_number,
    get_block,
    get_category,
    get_covalent_radius,
    get_electronegativity,
    get_element_symbol,
    get_group,
    get_mass_defect,
    get_nominal_mass,
    get_nominal_mass_from_formula,
    get_period,
    get_standard_atomic_weight,
    get_vdw_radius,
    is_valid_element,
    parse_formula,
    validate_isotopic_mass,
)
from cochem_base.path_sanitization import leak_patterns


@pytest.fixture
def atomic_data_file_path() -> Path:
    """Return absolute path to cochem_base/io/atomic_data.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "io" / "atomic_data.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


def test_file_encoding_and_lf_line_endings(atomic_data_file_path: Path) -> None:
    """Verify strictly Unix LF line endings (\n), standard UTF-8 encoding, and no BOM."""
    raw = atomic_data_file_path.read_bytes()
    assert b"\r\n" not in raw, "Found Windows CRLF (\r\n) line endings in atomic_data.py"
    assert b"\n" in raw, "Missing newline characters in atomic_data.py"
    assert not raw.startswith(b"\xef\xbb\xbf"), "Found UTF-8 BOM marker in atomic_data.py"


def test_zero_personal_path_leaks(atomic_data_file_path: Path) -> None:
    """Verify zero personal machine or local user path leakage in atomic_data.py."""
    lines = atomic_data_file_path.read_text(encoding="utf-8").splitlines()
    patterns = leak_patterns()
    leaks = []
    for lineno, line in enumerate(lines, 1):
        for pattern, placeholder in patterns:
            if pattern.search(line):
                leaks.append((lineno, placeholder, line.strip()))

    assert len(leaks) == 0, f"Detected personal path leaks in atomic_data.py: {leaks}"


def test_io_package_lazy_resolution() -> None:
    """Verify that cochem_base.io lazily exports PubChemAtomicDataValidator and all helpers."""
    validator_cls = getattr(io_pkg, "PubChemAtomicDataValidator")
    assert validator_cls is PubChemAtomicDataValidator

    hook_func = getattr(io_pkg, "validate_isotopic_mass")
    assert callable(hook_func)

    parse_fn = getattr(io_pkg, "parse_formula")
    assert callable(parse_fn)


def test_validator_instance_and_118_elements() -> None:
    """Verify all 118 periodic elements are present and structurally sound."""
    validator = get_atomic_data_validator()
    assert len(validator.elements) == 118

    # Verify atomic numbers 1 to 118 are contiguous and valid
    for z in range(1, 119):
        elem = validator.get_element_info(z)
        assert elem.atomic_number == z
        assert len(elem.symbol) in (1, 2)
        assert len(elem.name) > 0
        assert elem.standard_mass > 0.0
        assert elem.period is not None and 1 <= elem.period <= 7
        assert elem.block in ("s", "p", "d", "f")

        # Verify cross-lookups
        assert validator.get_atomic_number(elem.symbol) == z
        assert validator.get_element_symbol(z) == elem.symbol


def test_specific_element_properties() -> None:
    """Verify known physical properties for representative elements."""
    validator = get_atomic_data_validator()

    # Hydrogen
    h = validator.get_element_info("H")
    assert h.atomic_number == 1
    assert math.isclose(h.standard_mass, 1.008, rel_tol=1e-3)
    assert h.electronegativity == 2.20
    assert h.covalent_radius == 0.31
    assert h.vdw_radius == 1.20
    assert h.period == 1
    assert h.group == 1
    assert h.block == "s"
    assert h.category == "reactive_nonmetal"

    # Carbon
    c = validator.get_element_info("C")
    assert c.atomic_number == 6
    assert math.isclose(c.standard_mass, 12.011, rel_tol=1e-3)
    assert c.electronegativity == 2.55
    assert c.covalent_radius == 0.76
    assert c.vdw_radius == 1.70
    assert c.period == 2
    assert c.group == 14
    assert c.block == "p"
    assert c.category == "reactive_nonmetal"

    # Iron
    fe = validator.get_element_info("Fe")
    assert fe.atomic_number == 26
    assert math.isclose(fe.standard_mass, 55.845, rel_tol=1e-3)
    assert fe.period == 4
    assert fe.group == 8
    assert fe.block == "d"
    assert fe.category == "transition_metal"

    # Oganesson (Z=118)
    og = validator.get_element_info(118)
    assert og.symbol == "Og"
    assert og.name == "Oganesson"
    assert og.atomic_number == 118
    assert og.period == 7
    assert og.group == 18
    assert og.block == "p"
    assert og.category == "noble_gas"


def test_validate_isotopic_mass_valid_cases() -> None:
    """Test valid isotopic mass validations against PubChem known data."""
    # Hydrogen isotopes
    assert validate_isotopic_mass("H", 1, 1.007825) is True
    assert validate_isotopic_mass("H", 2, 2.014102) is True
    assert validate_isotopic_mass("H", 3, 3.016049) is True

    # Carbon isotopes
    assert validate_isotopic_mass("C", 12, 12.000000) is True
    assert validate_isotopic_mass("C", 13, 13.003355) is True
    assert validate_isotopic_mass("C", 14, 14.003242) is True

    # Oxygen & Nitrogen
    assert validate_isotopic_mass("O", 16, 15.994915) is True
    assert validate_isotopic_mass("N", 14, 14.003074) is True

    # Heavy element: Uranium
    assert validate_isotopic_mass("U", 238, 238.050788) is True


def test_validate_isotopic_mass_errors() -> None:
    """Test error handling and boundary conditions in isotopic validation."""
    validator = PubChemAtomicDataValidator()

    # Non-positive mass
    with pytest.raises(ValueError, match="Isotopic mass must be positive"):
        validator.validate_isotopic_mass("C", 12, -12.0)

    with pytest.raises(ValueError, match="Isotopic mass must be positive"):
        validator.validate_isotopic_mass("C", 12, 0.0)

    # Unreasonably large mass
    with pytest.raises(ValueError, match="Isotopic mass is unreasonably large"):
        validator.validate_isotopic_mass("C", 12, 350.0)

    # Unknown isotope of known element
    with pytest.raises(ValueError, match="Unknown isotope: C-99"):
        validator.validate_isotopic_mass("C", 99, 99.0)

    # Mass deviates beyond tolerance
    with pytest.raises(ValueError, match="deviates from expected"):
        validator.validate_isotopic_mass("C", 12, 12.2, tolerance=0.05)

    # Unknown element with large deviation
    with pytest.raises(ValueError, match="deviates too much from mass number"):
        validator.validate_isotopic_mass("UnknownElem", 50, 55.0)


def test_molecular_weight_calculations() -> None:
    """Test molecular weight and monoisotopic mass calculations."""
    # Water: H2O
    mw_water = calculate_molecular_weight({"H": 2, "O": 1})
    expected_water = 2 * 1.008 + 15.999
    assert math.isclose(mw_water, expected_water, rel_tol=1e-4)

    # Glucose: C6H12O6
    mw_glucose = calculate_molecular_weight({"C": 6, "H": 12, "O": 6})
    expected_glucose = 6 * 12.011 + 12 * 1.008 + 6 * 15.999
    assert math.isclose(mw_glucose, expected_glucose, rel_tol=1e-4)

    # Monoisotopic mass for H2O: 2 * 1.007825032 + 15.994914619
    mono_water = calculate_monoisotopic_mass({"H": 2, "O": 1})
    expected_mono = 2 * 1.007825032 + 15.994914619
    assert math.isclose(mono_water, expected_mono, rel_tol=1e-5)

    # Invalid negative atom count
    with pytest.raises(ValueError, match="Atom count cannot be negative"):
        calculate_molecular_weight({"H": -1, "O": 1})


def test_helper_getters() -> None:
    """Test module-level convenience getters."""
    assert get_atomic_number("Fe") == 26
    assert get_element_symbol(26) == "Fe"
    assert math.isclose(get_standard_atomic_weight("Au"), 196.97, rel_tol=1e-3)
    assert get_covalent_radius("Cl") == 1.02
    assert get_vdw_radius("Ar") == 1.88
    assert get_electronegativity("F") == 3.98
    assert get_period("Fe") == 4
    assert get_group("Fe") == 8
    assert get_block("Fe") == "d"
    assert get_category("Fe") == "transition_metal"

    # Invalid lookups
    with pytest.raises(ValueError, match="Unknown chemical element"):
        get_atomic_number("NonExistent")

    with pytest.raises(ValueError, match="No element found with atomic number"):
        get_element_symbol(999)


def test_most_abundant_isotopes_accuracy() -> None:
    """Test that monoisotopic mass and most abundant isotope accurately resolve
    to the highest-abundance isotope, especially where A != lowest mass number.
    """
    validator = get_atomic_data_validator()

    # Iron: most abundant is Fe-56 (91.75%), NOT Fe-54
    fe = validator.get_element_info("Fe")
    assert fe.most_abundant_isotope is not None
    assert fe.most_abundant_isotope.mass_number == 56
    assert math.isclose(fe.monoisotopic_mass, 55.9349375, rel_tol=1e-5)

    # Helium: He-4 (99.999%), NOT He-3
    he = validator.get_element_info("He")
    assert he.most_abundant_isotope.mass_number == 4

    # Lithium: Li-7 (92.41%), NOT Li-6
    li = validator.get_element_info("Li")
    assert li.most_abundant_isotope.mass_number == 7

    # Boron: B-11 (80.1%), NOT B-10
    b = validator.get_element_info("B")
    assert b.most_abundant_isotope.mass_number == 11

    # Argon: Ar-40 (99.6%), NOT Ar-36
    ar = validator.get_element_info("Ar")
    assert ar.most_abundant_isotope.mass_number == 40

    # Titanium: Ti-48 (73.7%)
    ti = validator.get_element_info("Ti")
    assert ti.most_abundant_isotope.mass_number == 48

    # Lead: Pb-208 (52.4%)
    pb = validator.get_element_info("Pb")
    assert pb.most_abundant_isotope.mass_number == 208


def test_formula_parser_simple_and_complex() -> None:
    """Test chemical formula parser for simple and nested formulas."""
    assert parse_formula("H2O") == {"H": 2, "O": 1}
    assert parse_formula("C6H12O6") == {"C": 6, "H": 12, "O": 6}
    assert parse_formula("NaCl") == {"Na": 1, "Cl": 1}
    assert parse_formula("Ca(OH)2") == {"Ca": 1, "O": 2, "H": 2}
    assert parse_formula("(NH4)2SO4") == {"N": 2, "H": 8, "S": 1, "O": 4}
    assert parse_formula("Fe3[Fe(CN)6]2") == {"Fe": 5, "C": 12, "N": 12}
    assert parse_formula("CH3COOH") == {"C": 2, "H": 4, "O": 2}


def test_formula_parser_hydrates_and_charges() -> None:
    """Test formula parser handling of hydrates, adducts, and ionic charges."""
    # Hydrates with asterisks and dots
    assert parse_formula("CuSO4*5H2O") == {"Cu": 1, "S": 1, "O": 9, "H": 10}
    assert parse_formula("CuSO4·5H2O") == {"Cu": 1, "S": 1, "O": 9, "H": 10}
    assert parse_formula("CuSO4.5H2O") == {"Cu": 1, "S": 1, "O": 9, "H": 10}

    # Ionic charges
    assert parse_formula("SO4^2-") == {"S": 1, "O": 4}
    assert parse_formula("NH4+") == {"N": 1, "H": 4}
    assert parse_formula("OH-") == {"O": 1, "H": 1}
    assert parse_formula("[Fe(CN)6]4-") == {"Fe": 1, "C": 6, "N": 6}


def test_formula_parser_errors() -> None:
    """Test error handling in chemical formula parser."""
    with pytest.raises(ValueError, match="Formula string cannot be empty"):
        parse_formula("")

    with pytest.raises(ValueError, match="Unbalanced"):
        parse_formula("Ca(OH")

    with pytest.raises(ValueError, match="Unbalanced"):
        parse_formula("Ca(OH))2")

    with pytest.raises(ValueError, match="Unknown chemical element symbol"):
        parse_formula("Xx2O")


def test_formula_direct_mass_calculators() -> None:
    """Test direct calculation of molecular weight and monoisotopic mass from formula."""
    mw = calculate_molecular_weight_from_formula("H2O")
    assert math.isclose(mw, 18.015, rel_tol=1e-3)

    mono = calculate_monoisotopic_mass_from_formula("H2O")
    assert math.isclose(mono, 18.01056, rel_tol=1e-4)

    nom = get_nominal_mass_from_formula("H2O")
    assert nom == 18


def test_nominal_mass_and_mass_defect() -> None:
    """Test nominal mass and mass defect calculations."""
    comp = {"C": 6, "H": 12, "O": 6}
    assert get_nominal_mass(comp) == 180

    defect = get_mass_defect(comp)
    assert isinstance(defect, float)
    assert abs(defect) < 0.2


def test_flexible_case_and_name_lookups() -> None:
    """Test case-insensitive symbol, IUPAC name, and atomic number lookups."""
    validator = get_atomic_data_validator()

    # Symbol casing
    assert validator.get_element_info("fe").symbol == "Fe"
    assert validator.get_element_info("FE").symbol == "Fe"
    assert validator.get_element_info("Fe").symbol == "Fe"

    # Name casing
    assert validator.get_element_info("iron").atomic_number == 26
    assert validator.get_element_info("Iron").atomic_number == 26
    assert validator.get_element_info("IRON").atomic_number == 26

    # String integer
    assert validator.get_element_info("26").symbol == "Fe"

    # is_valid_element
    assert is_valid_element("Fe") is True
    assert is_valid_element("iron") is True
    assert is_valid_element("NonExistentElement") is False


def test_isotope_info_properties() -> None:
    """Test IsotopeInfo model properties and immutability."""
    iso = IsotopeInfo(mass_number=13, mass=13.0033548, abundance=0.0107, is_stable=True)
    assert iso.mass_number == 13
    assert math.isclose(iso.mass_defect, 0.0033548, rel_tol=1e-5)

    # Immutability
    with pytest.raises(Exception):
        iso.mass = 14.0
