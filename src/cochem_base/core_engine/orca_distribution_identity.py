"""Public pinned ORCA distribution identity; contains no licensed payload.

Shared installer source and installed downstream clients use the same reviewed
identity. The companion regression binds this packaged identity to the exact
installer manifest bytes, including its digest.
"""

import copy

_MANIFEST = {'architecture': 'x86_64',
 'archive_name': 'orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz',
 'openmpi_version': '4.1.8',
 'orca_version': '6.1.1',
 'platform': 'Linux',
 'release_tag': 'orca-6.1.1',
 'repository': 'ProfJJK-CoChem/CoChem-ORCA',
 'schema_version': 1,
 'sha256': 'a0bc1d6d2c3c00620367bbc5dbf2b3a7018abc92d1ff65f06cec46f75350b9be',
 'source': 'User-provided private official distribution and independently '
           'calculated archive checksum'}
_MANIFEST_SHA256 = '913896cfe57ef69688619252e79a38acb84f137c725ad8039976285c5cabccc9'

def reviewed_orca_distribution() -> tuple[dict, str]:
    return copy.deepcopy(_MANIFEST), _MANIFEST_SHA256
