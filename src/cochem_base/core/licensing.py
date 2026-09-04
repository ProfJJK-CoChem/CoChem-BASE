"""Authoritative Machine-Readable SPDX Data Usage Licensing Schema.

Adheres strictly to FAIR Principle R1.1 and Method Matrix v4 open-science mandates.
Validates dataset and computational model reuse rights against approved SPDX license identifiers.
"""

from __future__ import annotations

from typing import Final, FrozenSet

OFFICIAL_SPDX_LICENSES: Final[FrozenSet[str]] = frozenset({
    "CC-BY-4.0",
    "CC0-1.0",
    "CC-BY-SA-4.0",
    "CC-BY-NC-4.0",
    "MIT",
    "Apache-2.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "GPL-3.0-only",
    "AGPL-3.0-only",
    "LGPL-3.0-only",
    "MPL-2.0",
    "ISC",
    "Unlicense",
})


def validate_spdx_license(license_id: str) -> str:
    """Validate that a license identifier conforms to approved SPDX open-science standards [D].

    Args:
        license_id: SPDX license expression string (e.g. 'CC-BY-4.0', 'MIT').

    Returns:
        str: Validated, stripped license identifier string.

    Raises:
        ValueError: If license_id is empty, invalid, or unrecognized in the SPDX table.
    """
    if not isinstance(license_id, str):
        raise ValueError(f"SPDX license identifier must be a string, got {type(license_id)}")

    clean_id = license_id.strip()
    if not clean_id:
        raise ValueError("SPDX license identifier cannot be empty.")

    if clean_id not in OFFICIAL_SPDX_LICENSES:
        raise ValueError(
            f"Invalid or unrecognized SPDX license identifier: '{clean_id}'. "
            f"Must be one of approved open-science identifiers: {sorted(OFFICIAL_SPDX_LICENSES)}"
        )

    return clean_id


__all__ = [
    "OFFICIAL_SPDX_LICENSES",
    "validate_spdx_license",
]
