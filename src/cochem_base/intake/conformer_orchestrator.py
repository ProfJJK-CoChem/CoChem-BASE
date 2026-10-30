"""Compatibility entry point for BASE's canonical physical conformer search.

The old implementation's fabricated zero-energy seed and swallowed engine errors
have been removed. The owned BASE broker executes the actual CREST/ORCA GOAT
request; every native member and sieve decision remains in retained artifacts.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Sequence

import numpy as np

from cochem_base.config_loader import get_artifact_dir
from cochem_base.geometry.nuclide_geometry import resolve_nuclear_identity
from cochem_base.intake.conformer_deduplication import (
    ConformerCandidate, ConformerDeduplicator, kabsch_quaternion_rmsd,
)
from cochem_base.interfaces.conformer import ConformerGenerator
from cochem_base.schemas import ConformerEnsemblePayload
from cochem_base.topos_runner import TOPOSExecutionBroker, TOPOSSearchConfig, _read_json


def kabsch_rmsd(p: np.ndarray, q: np.ndarray) -> float:
    """Delegate to the canonical proper-rotation Horn RMSD implementation."""
    return kabsch_quaternion_rmsd(p, q)


def deduplicate_union_ensemble(conformers: Sequence[dict[str, Any]],
                               delta_b_rel_threshold: float = .0005,
                               rmsd_threshold: float = .08) -> list[dict[str, Any]]:
    """Keep the list API while enforcing the complete canonical scientific sieve.

    Caller-supplied rotational constants are recomputed. Missing energy, state or
    comparison protocol retains the observation unranked rather than guessing.
    Use intake.conformer_engine for the complete source-bound lineage contract.
    """
    candidates = []
    for index, row in enumerate(conformers):
        energy = row.get("energy_hartree")
        unit = "hartree"
        if energy is None and row.get("energy") is not None:
            energy, unit = row["energy"], row.get("energy_unit")
            if unit not in {"hartree", "kcal/mol"}:
                raise ValueError("Conformer energy requires an explicit supported unit")
        candidates.append(ConformerCandidate(str(index), list(row["symbols"]),
            np.asarray(row.get("coordinates", row.get("coords")), dtype=float), energy,
            energy_unit=unit, charge=row.get("charge"), multiplicity=row.get("multiplicity"),
            comparison_protocol=row.get("comparison_protocol")))
    sieve = ConformerDeduplicator(rmsd_threshold=rmsd_threshold,
        rotational_constant_threshold=delta_b_rel_threshold).sieve(candidates, require_comparable_protocol=True)
    return [conformers[int(candidate.conformer_id)] for candidate in sieve.retained]


class ConformerOrchestrator(ConformerGenerator):
    """Synchronous compatibility wrapper around BASE's owned physical broker."""

    def __init__(self, ewin_kcal: float = 12.0) -> None:
        if isinstance(ewin_kcal, bool) or not np.isfinite(ewin_kcal) or not 0 < ewin_kcal <= 12:
            raise ValueError("The SRS conformer energy window must be positive and at most 12 kcal/mol")
        self.ewin_kcal = float(ewin_kcal)

    def generate_conformers(self, symbols: Sequence[str], coordinates: Sequence[Sequence[float]] | np.ndarray,
                            **kwargs: Any) -> ConformerEnsemblePayload:
        permitted = {"charge", "multiplicity", "ensemble_id", "max_hours", "threads_per_engine", "protocol",
                     "scratch_root", "store_root", "cancel_event"}
        if set(kwargs) - permitted:
            raise ValueError("Unsupported compatibility search options")
        if type(kwargs.get("charge")) is not int or type(kwargs.get("multiplicity")) is not int or kwargs["multiplicity"] < 1:
            raise ValueError("Conformer search requires explicit integer charge and multiplicity")
        identity = resolve_nuclear_identity(symbols)
        coords = np.asarray(coordinates, dtype=float)
        if coords.shape != (len(identity.nuclides), 3) or not np.isfinite(coords).all():
            raise ValueError("Conformer search requires complete finite coordinates")
        artifact_root = get_artifact_dir()
        source_dir = artifact_root / "Scratch" / ("compat-input-" + uuid.uuid4().hex)
        source_dir.mkdir(parents=True, exist_ok=False)
        source = source_dir / "input.xyz"
        source.write_text(str(len(symbols)) + "\nExplicit legacy API caller geometry; no observed energy\n" +
            "".join(label + " " + " ".join(format(value, ".17g") for value in position) + "\n"
                    for label, position in zip(identity.nuclides, coords, strict=True)), encoding="utf-8")
        broker = TOPOSExecutionBroker(kwargs.get("scratch_root"), kwargs.get("store_root"))
        config = TOPOSSearchConfig(input_xyz_path=str(source), atom_count=len(symbols),
            charge=kwargs["charge"], multiplicity=kwargs["multiplicity"], energy_window_kcal=self.ewin_kcal,
            protocol=kwargs.get("protocol", "CREST_GOAT"), max_hours=kwargs.get("max_hours", 2.0),
            threads_per_engine=kwargs.get("threads_per_engine", 1))
        job_id = broker.launch_search(config)
        try:
            while True:
                status = broker.poll_telemetry(job_id)
                if status["status"] != "RUNNING":
                    break
                event = kwargs.get("cancel_event")
                if event is not None and event.is_set():
                    broker.cancel_search(job_id)
                    raise RuntimeError("Physical conformer search was cancelled")
                time.sleep(.1)
            if status["status"] != "COMPLETED":
                raise RuntimeError("Physical conformer search did not complete: " + str(status.get("error") or status["status"]))
            promoted = broker.promote_artifacts(job_id)
            sieve = _read_json(promoted["promoted_dir"] / "pool-sieve.json")
            members = {row["conformer_id"]: row for row in sieve["members"]}
            return ConformerEnsemblePayload(ensemble_id=kwargs.get("ensemble_id", job_id),
                conformers=[members[member_id] for member_id in sieve["retained_ids"]],
                origin_engine=config.protocol, provenance_tag="[M]",
                metadata={"job_id": job_id, "artifact_directory": str(promoted["promoted_dir"]),
                          "n_raw": len(members), "n_unique": len(sieve["retained_ids"]),
                          "sieve": sieve, "scope": "Native screening; production relaxation and genuine minimum qualification remain required"})
        except BaseException:
            if broker.poll_telemetry(job_id)["status"] == "RUNNING":
                broker.cancel_search(job_id)
            raise


__all__ = ["kabsch_rmsd", "deduplicate_union_ensemble", "ConformerOrchestrator"]
