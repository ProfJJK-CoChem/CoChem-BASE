"""Classify exact reviewed non-scientific test controls during BASE source audit.

The anti-spoof linter remains strict and reports every interception. This policy
cannot authorize scientific results, engine substitutions, runtime skips or
other violation categories. The JSON binds complete owner bytes and exact call
sites. Separately reviewed owner and function AST digests below prevent a newly
regenerated JSON hash from authorizing a different target, helper or replacement.

The Win32 cleanup contract delegates to a captured real Popen and verifies
actual child reaping; its complete function is pinned, never generic Popen.
Codespaces orchestration uses text-only records and explicitly absent licensed
executables. Neither control establishes installation or physical acceptance.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

from ci_tools.anti_spoof_linter import Violation

# Source-review authorization, separate from the manifest's integrity records.
# Changes to any scope require reviewing the complete control and its effects.

APPROVED_OWNERS: dict[str, str] = {
    'tests/base/test_export_topos_evidence.py': 'a8771197e13d4ff07e65a7a8280085483a91651fa2ad029702f0ea6afe024694',
    'tests/base/test_lab_project_configuration.py': '476fb200ef3ff9974894933d38c01eec504483864613d43ccc0e186272bd62df',
    'tests/base/test_licensed_codespaces.py': '07fc50c6cabb10471910ae5ae2f76b208e92554047240e946f6bec4896c1ed81',
    'tests/base/test_mandatory_ecosystem.py': '63452abe832e34defb6e3f4c4e90eb5e46f70405a90591e17ca83c0e06f3536c',
    'tests/base/test_safe_subprocess_owned_cleanup.py': '066f83e806a9ab1247e2650b2485703ed0f621891d1d3190c4e7a5b3e06de3bf',
    'tests/base/test_topos_module_surfaces.py': '76b335bee278e1dece4d6b6fa868300b7de205cd71200ac28e6aa6725c59226b',
}

APPROVED_SCOPES: dict[tuple[str, str], str] = {
    ('tests/base/test_export_topos_evidence.py', 'test_failure_receipt_error_preserves_original_authority_failure'): 'baa505c157c0148ddb01e6335f1e7380330d11382d4a8630456d0e92444f6be8',
    ('tests/base/test_export_topos_evidence.py', 'test_rejected_installed_authority_has_no_raw_fallback'): '36eb97d668d058e8fc676c7bb9b225e08f3fa9cb9af92444094a615f564720dd',
    ('tests/base/test_lab_project_configuration.py', 'test_cli_success_and_failure_never_print_private_identifier'): '9cd038aec67337db29fd31108a88d8382d13b59c483073439afc17c4b9d29aa3',
    ('tests/base/test_licensed_codespaces.py', 'prepare_orca_control'): '99d0f9efefd726eb24caa6d2ce017d69d7a28f902a294a3020744f796e6d69bf',
    ('tests/base/test_licensed_codespaces.py', 'test_archive_checksum_failure_precedes_mpi_build_or_native_provision'): '66b7871f5b4657324d3fd64d5b25b2f4d78192469f91dc56fea73e2dbda62407',
    ('tests/base/test_licensed_codespaces.py', 'test_cfour_routing_persists_real_provider_environment_format_and_reuses_only_after_verification'): '6df0dcfe626504b8aba3b192c70ff3e8d526e275b6cc7c533efc03aa876d75fa',
    ('tests/base/test_licensed_codespaces.py', 'test_corrupt_mpi_source_cache_is_refused_before_credential_free_builder'): '7804ec0743fcc6f05b95b19ef7ce206015c269a19a22c2f999aacd74edc0283d',
    ('tests/base/test_licensed_codespaces.py', 'test_github_denial_does_not_echo_untrusted_token_bearing_cli_output'): '50879bc3cadd725ab7faa9f476af8e0865308ec7834a15c18511d63df618a087',
    ('tests/base/test_licensed_codespaces.py', 'test_installer_process_environment_uses_explicit_non_secret_inputs'): 'e66f585cad710ad9e5097564ba6b151aeaae0fc3e8a7985e0b5a701c487830f1',
    ('tests/base/test_licensed_codespaces.py', 'test_mpi_public_source_prefetch_retains_controller_proxy_before_scrubbed_builder'): '226f8c69cd4f64be2f9893f3a72ea811bd2e8b288f7c316cd7b3216843d6da98',
    ('tests/base/test_licensed_codespaces.py', 'test_project_visibility_and_identity_are_both_required'): '141c7211a3b9a7dfbd43c288248d51461419a18b3b5e95cfa6710c84337c1f0d',
    ('tests/base/test_licensed_codespaces.py', 'test_public_project_is_rejected_before_any_asset_access'): '3c0258dbff179a868410411a15f51c4576be3206e16d3bfce5f2b3f63c7a7b47',
    ('tests/base/test_licensed_codespaces.py', 'test_stage0_refresh_loads_persistent_paths_without_github_credentials'): '2cd4c6055f02ac367f9e312466860885b9480786b6bc6fe4d0adefe24141d58f',
    ('tests/base/test_licensed_codespaces.py', 'test_successful_provision_instruction_requires_running_dashboard_reload'): '6f900954f3c79ec99a5fdf6807168300578173ea411b2e8f463cc3fb0bb9773c',
    ('tests/base/test_licensed_codespaces.py', 'test_unrecorded_installation_refuses_overwrite_before_download'): '248828386fb7070e92ac3a7977017deaf091956eb02224431f9deb38781d3cd7',
    ('tests/base/test_mandatory_ecosystem.py', 'test_explicit_complete_kit_is_required_before_fetch_or_environment_creation'): 'b1fd2dbbab003b86d0ae405a97d78117d8f49facd0a20a5c9111387acd01e9ca',
    ('tests/base/test_mandatory_ecosystem.py', 'test_handoff_cli_does_not_convert_failed_provider_status_to_success'): 'fcea8e5fc426c8b1f166d18c7ea3505309e305894d6dd526bcce3afa9b97c693',
    ('tests/base/test_mandatory_ecosystem.py', 'test_new_setup_cannot_select_existing_runtime_or_silo_receipts'): 'c7522ad714527d1108da976667132dd525c69ef644eb58fef127f6b0420c1b97',
    ('tests/base/test_mandatory_ecosystem.py', 'test_pre_cancelled_handoff_cannot_invoke_a_provider'): '490f84e0cba938a463fa2980b5c30b0d60da4bb123d282bd52cc390df3b2a2ce',
    ('tests/base/test_mandatory_ecosystem.py', 'test_running_base_same_version_does_not_authorize_other_payload'): '577b42a413d59498b58e22fcb0d4a225286c21ed0152bbf4bd0dada9002e5016',
    ('tests/base/test_mandatory_ecosystem.py', 'test_self_consistent_kit_cannot_replace_catalog_pinned_module_wheels'): 'b83705616bfc3254ed0ad1c1d5a4116907cbcb9d24d9ce00110702c11673838e',
    ('tests/base/test_mandatory_ecosystem.py', 'test_source_archive_hash_alone_cannot_change_pinned_source'): '7dd147d2f8be9670d6441436200b3c72a719e689f5dc7783e4a2325f24e0a69a',
    ('tests/base/test_safe_subprocess_owned_cleanup.py', 'test_windows_assignment_uses_original_process_handle'): 'bd0001328d7d3c021df45e42631c1905f6a452d227f8ad14ff26399b3000fcdf',
    ('tests/base/test_safe_subprocess_owned_cleanup.py', 'test_windows_setup_failure_contract_never_leaves_a_started_child'): '0beeeaeb820ea7515da27fc55e9ec9493709c762feb10634af5ee26b1b23324f',
    ('tests/base/test_topos_module_surfaces.py', 'gui'): '96d581f81574d66fee76bad86122bf4728fe2006c6b26b75137955c24e6ae16f',
    ('tests/base/test_topos_module_surfaces.py', 'test_api_selection_rejects_untrusted_artifact_identity'): 'f088f83624556e477da64522c3ca33624b6ea75d71b96452043544d0a5ce9569',
    ('tests/base/test_topos_module_surfaces.py', 'test_batch_subprocess_failures_preserve_structured_results_and_continue'): '350a8cea38596074a6f9b388a39911e7276aa69a3da07f74adc218c4bbfe152d',
    ('tests/base/test_topos_module_surfaces.py', 'test_batch_topos_prerequisites_reject_before_install'): '0631c94af702a9c511ff9d030ee05961fcb0e5832f57f4a9463f82da1742251f',
    ('tests/base/test_topos_module_surfaces.py', 'test_dashboard_installer_uses_noneditable_base_and_explicit_kit'): '2a4383415d6b72a11252ee2d4edb49d989ce2612e7adf4b5a06b3d090cf8e66d',
    ('tests/base/test_topos_module_surfaces.py', 'test_gui_cancellation_reaches_execution_boundary_without_fake_success'): '6999069d9f799a3685379c842a2d180d924888d14b452506a316c6b9e20430d1',
    ('tests/base/test_topos_module_surfaces.py', 'test_gui_partial_result_is_never_rendered_as_completed_science'): '8abe00822d1bd5979d7fedc1bfb0858ca657135f348eb6d9aca3ab6e38244211',
    ('tests/base/test_topos_module_surfaces.py', 'test_interrupted_setup_keeps_actual_failed_process_audit_and_failed_batch'): 'a13fa684012e2c44cba2c3845618079b160f482f66dbcef0db8c769e01817627',
    ('tests/base/test_topos_module_surfaces.py', 'test_missing_kit_rejected_before_dashboard_bootstrap'): 'ccaca67701b39c78a30802a357b8ce30affe430dac839d38c2c87ec513cbb72b',
}



def ast_sha256(node: ast.AST) -> str:
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode("utf-8")).hexdigest()


def _index(tree: ast.AST) -> tuple[dict[str, ast.AST], dict[tuple[int, int], tuple[ast.Call, str]]]:
    scopes: dict[str, ast.AST] = {}
    calls: dict[tuple[int, int], tuple[ast.Call, str]] = {}

    def visit(node: ast.AST, stack: tuple[str, ...] = ()) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack = (*stack, node.name)
            scopes[".".join(stack)] = node
        if isinstance(node, ast.Call):
            calls[(node.lineno, node.col_offset)] = (node, ".".join(stack))
        for child in ast.iter_child_nodes(node):
            visit(child, stack)

    visit(tree)
    return scopes, calls


def _identity(call: ast.Call) -> tuple[str, str | None]:
    if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name) or call.func.value.id != "monkeypatch":
        raise ValueError("Reviewed controls must be exact monkeypatch fixture calls")
    args = call.args
    if call.func.attr == "setattr":
        if isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
            return args[0].value, ast.unparse(args[1])
        if not isinstance(args[1], ast.Constant) or not isinstance(args[1].value, str):
            raise ValueError("Reviewed attribute target must be explicit")
        return ast.unparse(args[0]) + "." + args[1].value, ast.unparse(args[2])
    if call.func.attr in {"setenv", "delenv"}:
        return "environment:" + ast.unparse(args[0]), ast.unparse(args[1]) if len(args) > 1 else None
    raise ValueError("Unsupported reviewed control mutation")


def validate_test_controls(root: Path, manifest: Path,
                           findings: dict[str, list[Violation]]) -> list[dict[str, Any]]:
    """Fail closed unless every registry entry exactly matches a reviewed site.

    Additional interceptions elsewhere remain blockers. Missing or extra entries
    within reviewed owner files fail rather than silently broadening the grant.
    """
    root = root.resolve()
    if manifest.is_symlink():
        raise ValueError("Reviewed control manifest cannot be a symlink")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if (payload.get("schema_version") != 1 or payload.get("scientific_acceptance") is not False
            or not isinstance(payload.get("controls"), list) or not payload["controls"]):
        raise ValueError("Invalid reviewed control manifest schema")
    owners = {path for path, _ in APPROVED_SCOPES}
    # Linter report containers use native OS path separators, while each
    # finding carries the canonical POSIX path produced by check_file. Bind
    # policy identity to that finding path, never its presentation-only key.
    observed = {(item.file_path, item.line, item.col) for rows in findings.values()
                for item in rows if item.category == "MONKEYPATCH_INTERCEPT" and item.file_path in owners}
    seen: set[tuple[str, int, int]] = set()
    cache: dict[str, tuple[str, dict[str, ast.AST], dict[tuple[int, int], tuple[ast.Call, str]]]] = {}
    records = []
    for entry in payload["controls"]:
        relative = entry.get("path")
        function = entry.get("function")
        if (not isinstance(relative, str) or not isinstance(function, str)
                or (relative, function) not in APPROVED_SCOPES):
            raise ValueError("Unreviewed test-control owner/function; production and native paths cannot be granted")
        if entry.get("category") != "MONKEYPATCH_INTERCEPT" or entry.get("scientific_execution_performed") is not False:
            raise ValueError("Control policy cannot waive this category or claim scientific execution")
        if not isinstance(entry.get("boundary"), str) or not entry["boundary"].strip():
            raise ValueError("Reviewed controls require an explicit non-scientific boundary")
        line, col = entry.get("line"), entry.get("col")
        if type(line) is not int or type(col) is not int or line < 1 or col < 0:
            raise ValueError("Invalid reviewed control source location")
        key = (relative, line, col)
        if key in seen:
            raise ValueError("Duplicate reviewed test-control entry")
        seen.add(key)
        if relative not in cache:
            path = root / relative
            if any(parent.is_symlink() for parent in [path, *path.parents] if parent.is_relative_to(root)):
                raise ValueError("Reviewed test control cannot use a symlink")
            if not path.is_file() or not path.resolve().is_relative_to(root / "tests" / "base"):
                raise ValueError("Reviewed control must be an existing BASE test file")
            scopes, calls = _index(ast.parse(path.read_text(encoding="utf-8-sig")))
            cache[relative] = hashlib.sha256(path.read_bytes()).hexdigest(), scopes, calls
        file_sha, scopes, calls = cache[relative]
        if entry.get("file_sha256") != file_sha or APPROVED_OWNERS[relative] != file_sha:
            raise ValueError("Reviewed control owner bytes changed")
        if function not in scopes:
            raise ValueError("Reviewed control function is absent")
        scope_sha = ast_sha256(scopes[function])
        if scope_sha != APPROVED_SCOPES[(relative, function)] or entry.get("function_ast_sha256") != scope_sha:
            raise ValueError("Reviewed control function changed; a fresh manifest hash is not authorization")
        call_scope = calls.get((line, col))
        if call_scope is None or call_scope[1] != function:
            raise ValueError("Reviewed control call location or function changed")
        call = call_scope[0]
        if entry.get("call_ast_sha256") != ast_sha256(call) or entry.get("call") != ast.unparse(call):
            raise ValueError("Reviewed control call AST changed")
        if (entry.get("target"), entry.get("replacement")) != _identity(call):
            raise ValueError("Reviewed control target or replacement changed")
        if key not in observed:
            raise ValueError("Stale or unused reviewed test-control entry")
        records.append(dict(entry))
    if seen != observed:
        raise ValueError("Review registry must cover exactly the observed control sites in reviewed owners")
    return records


def is_reviewed_control(item: Violation, records: list[dict[str, Any]]) -> bool:
    return item.category == "MONKEYPATCH_INTERCEPT" and any(
        item.file_path == record["path"] and item.line == record["line"] and item.col == record["col"]
        for record in records)
