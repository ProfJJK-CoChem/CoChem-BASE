"""CoChem-TORQ: Test Spin Contamination Validation for Unrestricted Calculations.

Compliant with Method Matrix v4 §8B.3 and Anti-Spoofing Directives.
Verifies Deliverable 8:
1. Resilient regex parsing across ORCA formatting variations (<S**2>, <S^2>, whitespace).
2. Mandatory spin extraction for unrestricted calculations (raising EcosystemExecutionError on missing <S^2>).
3. Broken-symmetry singlet (M=1, threshold <= 0.10) and multiplet (delta_spin <= 10%) validation.
4. Hard failure gate with ERR_SPIN_CONTAMINATION and user override support.
"""

import pytest
from cochem_base.exceptions import EcosystemExecutionError, SpinContaminationError
from Libraries.cochem_torq_engine import validate_spin_contamination
from Libraries.cochem_torq_parser import S2_PATTERN, parse_spin_contamination_s2


def test_s2_regex_parsing_variations():
    """Verify resilient regex parsing across diverse ORCA version output formats."""
    sample_outputs = [
        "Expectation value of <S**2> :   0.754123",
        "Expectation value of <S^2>  : 0.751000",
        "< S**2 > : 1.050",
        "<  S ^ 2  > :  0.0023",
        "Total <S**2> expectation value: 0.3500",
    ]
    expected_values = [0.754123, 0.751000, 1.050, 0.0023, 0.3500]

    for text, expected in zip(sample_outputs, expected_values):
        val = parse_spin_contamination_s2(text)
        assert val is not None
        assert pytest.approx(val, abs=1e-5) == expected


def test_open_shell_singlet_spin_contamination():
    """For an open-shell singlet (M=1), ideal=0.0. Observed 0.35 must abort with ERR_SPIN_CONTAMINATION."""
    # Singlet within tolerance (<S^2> <= 0.10)
    s_ideal, s_obs, dev = validate_spin_contamination(multiplicity=1, s_squared_observed=0.03)
    assert s_ideal == 0.0
    assert s_obs == 0.03

    # Singlet exceeding tolerance (0.35 > 0.10)
    with pytest.raises(SpinContaminationError) as excinfo:
        validate_spin_contamination(multiplicity=1, s_squared_observed=0.35)

    err_msg = str(excinfo.value)
    assert "ERR_SPIN_CONTAMINATION" in err_msg
    assert "0.3500" in err_msg

    # User override allows execution
    s_ideal, s_obs, dev = validate_spin_contamination(
        multiplicity=1, s_squared_observed=0.35, allow_spin_contamination=True
    )
    assert s_obs == 0.35


def test_doublet_multiplet_spin_contamination():
    """For a doublet (S=1/2, M=2), ideal=0.75.

    Observed 0.76 (1.3% deviation <= 10%) passes.
    Observed 0.90 (20% deviation > 10%) aborts with ERR_SPIN_CONTAMINATION.
    """
    # Doublet with 0.76: deviation |0.76 - 0.75| / 0.75 = 1.33% <= 10%
    s_ideal, s_obs, dev = validate_spin_contamination(multiplicity=2, s_squared_observed=0.76)
    assert s_ideal == 0.75
    assert s_obs == 0.76
    assert dev < 10.0

    # Doublet with 0.90: deviation |0.90 - 0.75| / 0.75 = 20.0% > 10%
    with pytest.raises(SpinContaminationError) as excinfo:
        validate_spin_contamination(multiplicity=2, s_squared_observed=0.90)

    err_msg = str(excinfo.value)
    assert "ERR_SPIN_CONTAMINATION" in err_msg
    assert "0.9000" in err_msg


def test_missing_spin_observable_raises_ecosystem_execution_error():
    """Unrestricted calculation missing <S^2> in output must raise EcosystemExecutionError."""
    unrestricted_output_without_s2 = (
        "ORCA TERMINATED NORMALLY\n"
        "FINAL SINGLE POINT ENERGY   -76.43820192\n"
    )

    with pytest.raises(EcosystemExecutionError) as excinfo:
        validate_spin_contamination(
            unrestricted_output_without_s2,
            multiplicity=2,
            is_unrestricted=True,
        )

    err_msg = str(excinfo.value)
    assert "[MISSING DATA]" in err_msg
    assert "Unrestricted calculation did not yield <S^2>" in err_msg
