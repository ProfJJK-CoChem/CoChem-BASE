"""
test_cli_audit.py
=================
Comprehensive unit and integration tests for cli.py and cochem_base.cli.
Mandated by SRS Doc 2 Part 1 (§1.6) and Method Matrix v4.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import cli  # noqa: E402
import cochem_base.cli as cochem_base_cli  # noqa: E402


class TestCliParser:
    """Validates CLI argument parsing structure and subcommands."""

    def test_parser_creation(self) -> None:
        parser = cli.build_cli_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "cochem-cli"

    def test_subcommand_presence(self) -> None:
        parser = cli.build_cli_parser()
        subparsers_action = [
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        ]
        assert len(subparsers_action) == 1
        choices = subparsers_action[0].choices
        for expected in ["setup", "audit", "preflight", "status", "info", "phase", "clean", "mass", "element"]:
            assert expected in choices, f"Expected subcommand '{expected}' not found in parser."

    def test_version_action(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = cli.build_cli_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "CoChem-BASE" in captured.out or "CoChem-BASE" in captured.err

    def test_no_args_returns_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        code = cli.main([])
        assert code == 0
        captured = capsys.readouterr()
        assert "CoChem-BASE" in captured.out


class TestCliPhaseLoading:
    """Validates dynamic loading of setup phases 1 through 11."""

    @pytest.mark.parametrize("phase_num", list(range(1, 12)))
    def test_load_all_valid_phases(self, phase_num: int) -> None:
        func = cli.load_phase_callable(phase_num)
        assert callable(func)
        assert phase_num in cli.PHASE_METADATA
        meta = cli.PHASE_METADATA[phase_num]
        assert "name" in meta
        assert "desc" in meta
        assert "module" in meta
        assert "func" in meta

    def test_invalid_phase_number(self) -> None:
        with pytest.raises(ValueError):
            cli.load_phase_callable(0)
        with pytest.raises(ValueError):
            cli.load_phase_callable(12)


class TestCliPhaseExecution:
    """Tests dry-run execution of representative phases."""

    def test_execute_phase_1_dry_run(self) -> None:
        success, status_str, report = cli.execute_phase(1, dry_run=True)
        assert status_str in ("PASSED", "DEGRADED")
        assert "phase_id" in report
        assert "execution_time_sec" in report

    def test_execute_phase_2_dry_run(self) -> None:
        success, status_str, report = cli.execute_phase(2, dry_run=True)
        assert success is True
        assert status_str == "PASSED"
        assert report["status"] == "PASSED"
        assert "cpu" in report or "hardware" in report or "memory" in report

    def test_execute_phase_3_dry_run(self) -> None:
        success, status_str, report = cli.execute_phase(3, dry_run=True)
        assert status_str in ("PASSED", "DEGRADED")
        assert "engines" in report


class TestCliSubcommands:
    """Tests high-level action functions of cli.py."""

    def test_action_audit_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = cli.build_cli_parser()
        args = parser.parse_args(["audit", "--json"])
        code = cli.action_audit(args)
        assert code in (0, 1)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "host" in data
        assert "audits" in data

    def test_action_status_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = cli.build_cli_parser()
        args = parser.parse_args(["status", "--json"])
        code = cli.action_status(args)
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "artifact_directory" in data
        assert "phase_artifacts" in data

    def test_action_mass_valid_element(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = cli.build_cli_parser()
        args = parser.parse_args(["mass", "C", "--json"])
        code = cli.action_mass(args)
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["symbol"] == "C"
        assert data["element"] == "Carbon"
        assert data["standard_atomic_weight"] > 12.0

    def test_action_mass_valid_isotope(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = cli.build_cli_parser()
        args = parser.parse_args(["mass", "13C", "--json"])
        code = cli.action_mass(args)
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["symbol"] == "C"
        assert "requested_isotope" in data
        assert data["requested_isotope"]["mass_number"] == 13
        assert abs(data["requested_isotope"]["mass"] - 13.0033548) < 1e-4

    def test_action_mass_invalid_symbol(self) -> None:
        parser = cli.build_cli_parser()
        args = parser.parse_args(["mass", "UnknownElement999", "--json"])
        code = cli.action_mass(args)
        assert code == 1

    def test_action_phase_direct(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = cli.build_cli_parser()
        args = parser.parse_args(["phase", "2", "--dry-run", "--json"])
        code = cli.action_phase(args)
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data.get("status") == "PASSED"

    def test_action_setup_subset_dry_run(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = cli.build_cli_parser()
        args = parser.parse_args(["setup", "-p", "1", "2", "--dry-run", "--json"])
        code = cli.action_setup(args)
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["overall_status"] == "PASSED"
        assert len(data["phases_executed"]) == 2

    def test_action_clean_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = cli.build_cli_parser()
        args = parser.parse_args(["clean", "--json"])
        code = cli.action_clean(args)
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "CLEAN_COMPLETE"
        assert "sandboxes_purged" in data



class TestPackageExportParity:
    """Ensures cochem_base.cli provides identical interface and exports."""

    def test_module_exports(self) -> None:
        for name in [
            "PHASE_METADATA", "TermColor", "action_setup", "action_audit",
            "action_status", "action_phase", "action_clean", "action_mass",
            "build_cli_parser", "main", "execute_phase", "load_phase_callable"
        ]:
            assert hasattr(cochem_base_cli, name)
            assert getattr(cochem_base_cli, name) is getattr(cli, name)
