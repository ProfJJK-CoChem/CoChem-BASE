"""Canonical data-only conformer-pool union and SRS sieve.

CREST, GOAT and imported structure records enter the same canonical sieve.
This module never launches a substitute search, fabricates a seed energy, or
certifies imported energies as measured by BASE. Original records and every
retention/exclusion decision remain available to the GUI and downstream modules.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
from typing import Any, Sequence

import numpy as np

from .conformer_deduplication import ConformerCandidate, ConformerDeduplicator
from cochem_base.physics.isotopes import GHOST_ATOMS, parse_nuclide_token
from cochem_base.physics.nuclide_resolver import get_element


def sieve_ingested_records(records: Sequence[dict[str, Any]], *, charge: int | None = None,
                           multiplicity: int | None = None,
                           comparison_protocol: str | None = None) -> dict[str, Any]:
    """Preserve all heterogeneous pool observations and rank only comparable ones.

    A GUI may supply explicit common electronic state and comparison protocol.
    They fill unknown fields; a conflicting source declaration rejects the union.
    Composition, isotope identity, charge, spin and protocol define independent
    energy windows. Without that evidence a record is retained as unranked.
    """
    if isinstance(records, (str, bytes)) or not isinstance(records, (list, tuple)):
        raise ValueError("Conformer union requires an explicit list of ingested records")
    if charge is not None and type(charge) is not int:
        raise ValueError("Pool charge must be an explicit integer or unknown")
    if multiplicity is not None and (type(multiplicity) is not int or multiplicity < 1):
        raise ValueError("Pool multiplicity must be a positive integer or unknown")
    if comparison_protocol is not None and (not isinstance(comparison_protocol, str) or not comparison_protocol.strip()):
        raise ValueError("Pool comparison protocol must be explicitly identified or unknown")
    original, candidates, by_id = [], [], {}
    for index, source in enumerate(records):
        if not isinstance(source, dict):
            raise ValueError("Every ingested conformer member must be a data record")
        original_record = deepcopy(source)
        record = deepcopy(source)
        json.dumps(record, allow_nan=False)
        digest = record.get("source_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("Every conformer member requires its original source SHA-256")
        frame = record.get("record_index")
        if type(frame) is not int or frame < 0:
            raise ValueError("Every conformer member requires its original nonnegative frame index")
        symbols = record.get("symbols")
        coordinates = record.get("coords", record.get("coordinates"))
        if not isinstance(symbols, list) or any(not isinstance(label, str) for label in symbols):
            raise ValueError("Conformer pool members require their complete ordered nuclear symbols")
        for field, shared in (("charge", charge), ("multiplicity", multiplicity), ("comparison_protocol", comparison_protocol)):
            supplied = record.get(field)
            if supplied is not None and shared is not None and supplied != shared:
                raise ValueError("Source conformer declaration conflicts with the common pool " + field)
            if supplied is None and shared is not None:
                record[field] = shared
        state_charge, state_spin = record.get("charge"), record.get("multiplicity")
        if state_charge is not None and type(state_charge) is not int:
            raise ValueError("Source charge must be an explicit integer or unknown")
        if state_spin is not None and (type(state_spin) is not int or state_spin < 1):
            raise ValueError("Source multiplicity must be a positive integer or unknown")
        if state_charge is not None and state_spin is not None:
            electrons = sum(0 if parse_nuclide_token(label)[0].upper() in GHOST_ATOMS else
                            int(get_element(parse_nuclide_token(label)[0]).atomic_number) for label in symbols) - state_charge
            unpaired = state_spin - 1
            if electrons < unpaired or (electrons - unpaired) % 2:
                raise ValueError("Source charge/multiplicity contradict the nuclear electron count")
        protocol = record.get("comparison_protocol")
        if protocol is not None and (not isinstance(protocol, str) or not protocol.strip()):
            raise ValueError("Source comparison protocol must be explicit or unknown")
        energy = record.get("imported_energy")
        unit = record.get("imported_energy_unit")
        if energy is not None and (type(energy) not in {int, float} or not math.isfinite(energy)):
            raise ValueError("An imported pool energy must be a finite measured number or unknown")
        if energy is not None and unit not in {"hartree", "kcal/mol"}:
            raise ValueError("An imported pool energy requires its explicit supported unit")
        # Repeated uploads remain distinct lineage observations. Their original
        # source and frame identities remain unchanged in each source dictionary.
        identity = json.dumps([digest, frame, record.get("source_filename"), index], separators=(",", ":"))
        member_id = "pool-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
        candidate = ConformerCandidate(member_id, list(symbols), np.asarray(coordinates, dtype=float), energy,
            energy_unit=unit if energy is not None else "hartree", source=digest,
            charge=state_charge, multiplicity=state_spin, comparison_protocol=protocol,
            metadata={"original_record_index": index})
        original.append(original_record)
        candidates.append(candidate)
        by_id[member_id] = record
    result = ConformerDeduplicator().sieve(candidates, require_comparable_protocol=True)
    return {"schema_version": "cochem.conformer-pool-sieve/1", "count": len(original),
            "unique_count": len(result.retained), "records": original,
            "member_ids": [member.conformer_id for member in candidates],
            "declared_context": {"charge": charge, "multiplicity": multiplicity, "comparison_protocol": comparison_protocol},
            "unique_records": [by_id[member.conformer_id] for member in result.retained],
            "decisions": [asdict(decision) for decision in result.decisions],
            "parameters": {"rmsd_threshold_angstrom": 0.08, "rotational_constant_relative_threshold": 0.0005,
                           "energy_window_kcal_mol": 12.0, "duplicate_energy_threshold_kcal_mol": 0.05,
                           "wl_iterations": 3, "max_exact_permutations": 720},
            "scope": "Canonical imported pool union and spectroscopic sieve. All source records remain in lineage; imported energies are not a BASE execution/convergence certificate. Unknown energies, states or comparison protocols remain unranked and retained."}


__all__ = ["sieve_ingested_records"]
