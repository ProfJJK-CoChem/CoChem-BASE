"""Select native GitHub CLI authentication for private lifecycle subprocesses.

This selects only process environment variable names. The genuine GitHub CLI
owns stored browser credentials; this module never obtains or reads them.
Actions always retains its actual owning-project environment authentication.
"""

from __future__ import annotations

import os
from collections.abc import Mapping


def private_gh_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Avoid Codespaces token shadowing without changing the parent process.

    ``auto`` selects stored native CLI authentication in Codespaces and injected
    authentication elsewhere. Explicit ``stored-cli`` and ``environment`` modes
    support authorized local choices. Every override is ignored in Actions.
    """
    selected = dict(os.environ if environment is None else environment)
    if selected.get("GITHUB_ACTIONS", "").lower() == "true":
        return selected
    mode = selected.get("COCHEM_PRIVATE_GH_AUTH", "auto")
    if mode not in {"auto", "stored-cli", "environment"}:
        raise ValueError("COCHEM_PRIVATE_GH_AUTH must be auto, stored-cli, or environment.")
    use_stored = mode == "stored-cli" or (
        mode == "auto" and selected.get("CODESPACES", "").lower() == "true"
    )
    if use_stored:
        selected.pop("GH_TOKEN", None)
        selected.pop("GITHUB_TOKEN", None)
    return selected
