#!/usr/bin/env python3
"""Bind an existing private personal project to its own Actions secret names.

Organization Actions secrets do not propagate to personal repositories. This
command never creates a credential, reads a secret value, enables Actions, or
certifies a licensed installation. The repository owner must first add their
authorized archive-read credential as a repository Actions secret.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable

SELECTOR_VARIABLES = (
    "COCHEM_ORCA_ACCESS_SECRET",
    "COCHEM_CFOUR_ACCESS_SECRET",
)
_OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
_PROJECT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")
_SECRET_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class ProjectConfigurationError(RuntimeError):
    """A sanitized error with an honest record of attempted variable writes."""

    def __init__(self, message: str, *, phase: str = "preflight",
                 attempted: tuple[str, ...] = (), completed: tuple[str, ...] = ()):
        super().__init__(message)
        self.phase = phase
        self.attempted = attempted
        self.completed = completed

    def report(self) -> dict:
        return {
            "configuration_status": "incomplete",
            "phase": self.phase,
            "error": str(self),
            "variables_attempted": list(self.attempted),
            "variable_writes_completed": list(self.completed),
            "changes_may_have_occurred": bool(self.attempted),
            "scientific_acceptance": "not-run",
        }


def _secret_name(value: str) -> str:
    if (not isinstance(value, str) or not _SECRET_NAME.fullmatch(value)
            or value.upper().startswith("GITHUB_")):
        raise ProjectConfigurationError("The credential selector is not a valid repository secret name.")
    return value.upper()


def _repository(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or value.count("/") != 1:
        raise ProjectConfigurationError("Repository must be an OWNER/PROJECT identity.")
    owner, project = value.split("/")
    if not _OWNER.fullmatch(owner) or "--" in owner or not _PROJECT.fullmatch(project):
        raise ProjectConfigurationError("Repository must be a valid OWNER/PROJECT identity.")
    return owner, project


class GitHubCLI:
    """Use GitHub's API through gh without shell expansion or diagnostic echo."""

    def __init__(self, run: Callable | None = None):
        self.run = run or subprocess.run

    def request(self, endpoint: str, *, method: str = "GET", body: dict | None = None,
                paginate: bool = False):
        command = ["gh", "api", "--hostname", "github.com", "--method", method, endpoint]
        if paginate:
            command.append("--paginate")
        if body is not None:
            # Selector values stay off the process argument list. No token value
            # is read by this command; gh uses the caller's existing login.
            command.extend(["--input", "-"])
        try:
            result = self.run(command, input=None if body is None else json.dumps(body),
                              text=True, capture_output=True, check=False, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            raise ProjectConfigurationError("GitHub CLI could not complete the API request.") from None
        if result.returncode != 0:
            # HTTP diagnostics may contain identifiers or credentials. Neither
            # stdout nor stderr is suitable for a public configuration receipt.
            raise ProjectConfigurationError("GitHub API request failed; check gh authentication and repository permissions.")
        if not result.stdout.strip():
            return None
        try:
            if paginate:
                # gh releases before --slurp print successive JSON documents.
                # Pages can span lines or be adjacent; line splitting loses
                # those boundaries and accepting a prefix hides malformed data.
                decoder = json.JSONDecoder()
                remaining = result.stdout.lstrip()
                pages = []
                while remaining:
                    page, end = decoder.raw_decode(remaining)
                    pages.append(page)
                    remaining = remaining[end:].lstrip()
                return pages
            return json.loads(result.stdout)
        except (ValueError, TypeError):
            raise ProjectConfigurationError("GitHub API returned an invalid configuration response.") from None


def _items(pages, key: str) -> list[dict]:
    if not isinstance(pages, list) or not pages:
        raise ProjectConfigurationError("GitHub API returned an incomplete configuration inventory.")
    result = []
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get(key), list):
            raise ProjectConfigurationError("GitHub API returned an invalid configuration inventory.")
        for item in page[key]:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise ProjectConfigurationError("GitHub API returned an invalid configuration inventory.")
            result.append(item)
    return result


def _variables(client: GitHubCLI, prefix: str) -> dict[str, str]:
    result = {}
    for item in _items(client.request(f"{prefix}/actions/variables", paginate=True), "variables"):
        if not isinstance(item.get("value"), str) or item["name"] in result:
            raise ProjectConfigurationError("GitHub API returned an invalid variable inventory.")
        result[item["name"]] = item["value"]
    return result


def configure_project(repository: str, credential_name: str | None = None, *,
                      check_only: bool = False, client: GitHubCLI | None = None) -> dict:
    """Check ownership and privacy before selecting existing repository secrets."""
    owner, _ = _repository(repository)
    if credential_name is None and not check_only:
        raise ProjectConfigurationError("Configuring a project requires an existing repository credential name.")
    credential = None if credential_name is None else _secret_name(credential_name)
    client = client or GitHubCLI()
    prefix = f"repos/{repository}"
    account = client.request("user")
    if not isinstance(account, dict) or not isinstance(account.get("login"), str):
        raise ProjectConfigurationError("GitHub API did not identify the authenticated account.")
    if account["login"].casefold() != owner.casefold():
        raise ProjectConfigurationError("The authenticated account must own this personal project repository.")
    project = client.request(prefix)
    if not isinstance(project, dict):
        raise ProjectConfigurationError("GitHub API did not identify the project repository.")
    if project.get("private") is not True or project.get("visibility", "private") != "private":
        raise ProjectConfigurationError("Licensed asset selectors require a private project repository.")
    repo_owner = project.get("owner")
    if (not isinstance(repo_owner, dict) or repo_owner.get("type") != "User"
            or not isinstance(repo_owner.get("login"), str)
            or repo_owner["login"].casefold() != owner.casefold()
            or not isinstance(project.get("full_name"), str)
            or project["full_name"].casefold() != repository.casefold()):
        raise ProjectConfigurationError("This command supports only a personal repository owned by the authenticated account.")
    if project.get("archived") or project.get("disabled"):
        raise ProjectConfigurationError("The project repository must be active.")
    permissions = client.request(f"{prefix}/actions/permissions")
    if not isinstance(permissions, dict) or permissions.get("enabled") is not True:
        raise ProjectConfigurationError("GitHub Actions must be enabled before configuring this project.")
    secret_names = {
        _secret_name(item["name"])
        for item in _items(client.request(f"{prefix}/actions/secrets", paginate=True), "secrets")
    }
    if credential is not None and credential not in secret_names:
        raise ProjectConfigurationError("The selected repository Actions secret does not exist.")
    variables = _variables(client, prefix)
    if check_only:
        for name in SELECTOR_VARIABLES:
            if name not in variables:
                raise ProjectConfigurationError("A required licensed asset selector variable is missing.")
            selected = _secret_name(variables[name])
            if selected not in secret_names:
                raise ProjectConfigurationError("A licensed asset selector references a missing repository Actions secret.")
            if credential is not None and selected != credential:
                raise ProjectConfigurationError("The project selectors do not match the requested credential.")
        return _success(repository, "checked", ())

    attempted: list[str] = []
    completed: list[str] = []
    try:
        for name in SELECTOR_VARIABLES:
            if variables.get(name) == credential:
                continue
            attempted.append(name)
            if name in variables:
                client.request(f"{prefix}/actions/variables/{name}", method="PATCH",
                               body={"name": name, "value": credential})
            else:
                client.request(f"{prefix}/actions/variables", method="POST",
                               body={"name": name, "value": credential})
            completed.append(name)
    except ProjectConfigurationError as error:
        raise ProjectConfigurationError(str(error), phase="variable-write",
                                        attempted=tuple(attempted), completed=tuple(completed)) from None
    try:
        readback = _variables(client, prefix)
        if any(readback.get(name) != credential for name in SELECTOR_VARIABLES):
            raise ProjectConfigurationError("The repository selector readback did not match the requested configuration.")
    except ProjectConfigurationError as error:
        raise ProjectConfigurationError(str(error), phase="readback",
                                        attempted=tuple(attempted), completed=tuple(completed)) from None
    return _success(repository, "configured", tuple(completed))


def _success(repository: str, status: str, completed: tuple[str, ...]) -> dict:
    return {
        "configuration_status": status,
        "repository": repository,
        "repository_scope": "private-personal",
        "selector_variables": list(SELECTOR_VARIABLES),
        "variable_writes_completed": list(completed),
        "credential_values_read": False,
        "archive_access_verified": False,
        "scientific_acceptance": "not-run",
    }


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error can echo a private selector entered incorrectly.
        self.print_usage(sys.stderr)
        self.exit(2, "Invalid command line; see --help.\n")


def main(argv: list[str] | None = None, *, client: GitHubCLI | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--repository", required=True, metavar="OWNER/PROJECT")
    parser.add_argument("--credential-name", metavar="EXISTING_SECRET_NAME",
                        help="Existing repository Actions secret name; required unless checking only.")
    parser.add_argument("--check-only", action="store_true",
                        help="Inspect existing selectors and secret names without making any changes.")
    args = parser.parse_args(argv)
    try:
        result = configure_project(args.repository, args.credential_name,
                                   check_only=args.check_only, client=client)
    except ProjectConfigurationError as error:
        print(json.dumps(error.report(), sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
