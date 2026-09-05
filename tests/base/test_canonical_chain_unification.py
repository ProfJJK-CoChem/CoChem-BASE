"""CoChem-BASE: Test Canonical State-Chaining Engine Unification across Ecosystem.

Compliant with Method Matrix §8B, §8C, Suggestion #78, #157, and Anti-Spoofing Directives.
Verifies Deliverable 7:
1. Canonical exports from cochem_base.chain package (Chain, ChainStage, Stage, StateChainingAuditor).
2. Module-level exports from cochem_base.chain.chain and cochem_base.chain.auditor.
3. Facade re-exports from CoChem-TOPOS/chain.py and CoChem-TORQ/Libraries/chain.py match canonical classes.
4. Method Matrix §8B.5 Rules D1-D5 verification via StateChainingAuditor.
5. Canonical 11-Arrow mapping and chain configuration integrity.
"""

import importlib.util
import sys
from pathlib import Path

from cochem_base.chain import (
    CANONICAL_ARROWS,
    CanonicalArrow,
    Chain,
    ChainStage,
    Stage,
    StateChainingAuditor,
)
from cochem_base.chain.auditor import StateChainingAuditor as SubAuditor
from cochem_base.chain.chain import Chain as SubChain


def _import_module_from_path(module_name: str, file_path: Path):
    """Dynamically load module from absolute path."""
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_canonical_chain_package_exports():
    """Verify public exports from cochem_base.chain package."""
    assert Chain is SubChain
    assert StateChainingAuditor is SubAuditor
    assert ChainStage is Stage
    assert len(CANONICAL_ARROWS) == 11
    assert CanonicalArrow.ARROW_1_MLFF_XTB_GOAT == 1
    assert CanonicalArrow.ARROW_11_COMPOUND_CHAIN == 11


def test_topos_facade_reexports():
    """Verify CoChem-TOPOS/chain.py re-exports canonical cochem_base.chain classes."""
    topos_chain_path = Path("D:/__CoChem/GitHub-Repo/CoChem-TOPOS/chain.py")
    assert topos_chain_path.exists()

    topos_chain_mod = _import_module_from_path("topos_chain_facade", topos_chain_path)
    assert topos_chain_mod.Chain is Chain
    assert topos_chain_mod.ChainStage is ChainStage
    assert topos_chain_mod.StateChainingAuditor is StateChainingAuditor


def test_torq_facade_reexports():
    """Verify CoChem-TORQ/Libraries/chain.py re-exports canonical cochem_base.chain classes."""
    torq_chain_path = Path("D:/__CoChem/GitHub-Repo/CoChem-TORQ/Libraries/chain.py")
    assert torq_chain_path.exists()

    torq_chain_mod = _import_module_from_path("torq_chain_facade", torq_chain_path)
    assert torq_chain_mod.Chain is Chain
    assert torq_chain_mod.ChainStage is ChainStage
    assert torq_chain_mod.StateChainingAuditor is StateChainingAuditor


def test_state_chaining_auditor_rules_d1_to_d5():
    """Verify StateChainingAuditor correctly audits Method Matrix §8B.5 Rules D1-D5."""
    # Rule D1: Stationarity
    pass_d1, _ = StateChainingAuditor.audit_d1_stationarity(gradient_norm_hartree_bohr=5e-6, tol_max_g=1e-5)
    fail_d1, _ = StateChainingAuditor.audit_d1_stationarity(gradient_norm_hartree_bohr=2e-4, tol_max_g=1e-5)
    assert pass_d1 is True
    assert fail_d1 is False

    # Rule D2: Hessian transfer
    pass_d2, _ = StateChainingAuditor.audit_d2_hessian_transfer(harmonic_frequencies_cm1=[150.0, 300.0, 1600.0])
    fail_d2, _ = StateChainingAuditor.audit_d2_hessian_transfer(harmonic_frequencies_cm1=[-50.0, 300.0, 1600.0])
    assert pass_d2 is True
    assert fail_d2 is False

    # Rule D3: SCF stability
    pass_d3, _ = StateChainingAuditor.audit_d3_scf_stability(fresh_energy_hartree=-76.4000001, reused_energy_hartree=-76.4000001)
    fail_d3, _ = StateChainingAuditor.audit_d3_scf_stability(fresh_energy_hartree=-76.4000000, reused_energy_hartree=-76.3990000)
    assert pass_d3 is True
    assert fail_d3 is False

    # Rule D4: Counterpoise hygiene
    pass_d4, _ = StateChainingAuditor.audit_d4_counterpoise_hygiene(stage_name="dimer_opt", counterpoise="none", mo_from=None)
    fail_d4, _ = StateChainingAuditor.audit_d4_counterpoise_hygiene(stage_name="monomer_a", counterpoise="monomer", mo_from="dimer_opt")
    assert pass_d4 is True
    assert fail_d4 is False

    # Rule D5: Naming hygiene
    pass_d5, _ = StateChainingAuditor.audit_d5_naming_hygiene(current_stage="s3", consumed_stage="s2")
    fail_d5, _ = StateChainingAuditor.audit_d5_naming_hygiene(current_stage="s2", consumed_stage="s2")
    assert pass_d5 is True
    assert fail_d5 is False
