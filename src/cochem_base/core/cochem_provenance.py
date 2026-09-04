"""Authoritative W3C PROV-O Conformer Lineage & Semantic Provenance Graphs.

Complies strictly with:
- W3C PROV-O Linked Data Standard (prov:Entity, prov:Activity, prov:wasDerivedFrom)
- Tripartite Air-Gap Mandate (Offline local JSON-LD context catalog resolution)
- FAIR Principles I1, I3, and R1.2
- Method Matrix v4 §8B.4 & §9B (Quasi-Harmonic Thermodynamics Provenance)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from cochem_base.core.models import ThermodynamicsProvenance


def get_local_prov_context() -> Dict[str, Any]:
    """Retrieve bundled offline local W3C PROV-O JSON-LD context [D].

    Dispatches zero network calls to http://www.w3.org/ns/prov#, guaranteeing air-gapped execution.
    """
    ctx_path = Path(__file__).resolve().parent.parent / "schemas" / "contexts" / "prov_o_context.jsonld"
    if not ctx_path.exists():
        candidates = [
            Path(__file__).resolve().parent / "prov_o_context.jsonld",
            Path(__file__).resolve().parents[2] / "schemas" / "contexts" / "prov_o_context.jsonld",
        ]
        for cand in candidates:
            if cand.exists():
                ctx_path = cand
                break

    if not ctx_path.exists():
        raise FileNotFoundError(f"Offline local JSON-LD context not found at expected path: {ctx_path}")

    return json.loads(ctx_path.read_text(encoding="utf-8"))


class DAGNode(BaseModel):
    """Semantic Directed Acyclic Graph (DAG) node representing conformers or computational workflows."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    node_id: str = Field(..., description="Unique node identifier within the lineage graph")
    node_type: Literal["entity", "activity", "agent"] = Field(
        default="entity", description="PROV-O class classification"
    )
    activity_type: Optional[str] = Field(
        default=None, description="Specific activity type URI or curie (e.g. 'cochem:Optimization')"
    )
    parents: List[str] = Field(
        default_factory=list, description="Identifiers of ancestor nodes (prov:wasDerivedFrom)"
    )
    activity: Optional[str] = Field(
        default=None, description="Identifier of generating activity (prov:wasGeneratedBy)"
    )
    started_at_time: Optional[str] = Field(
        default=None, description="ISO 8601 UTC start timestamp"
    )
    ended_at_time: Optional[str] = Field(
        default=None, description="ISO 8601 UTC completion timestamp"
    )
    relative_energy_kcal_mol: Optional[float] = Field(
        default=None, description="Relative electronic energy in kcal/mol"
    )
    rotational_constants_mhz: Optional[List[float]] = Field(
        default=None, description="Principal rotational constants [A, B, C] in MHz"
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary execution payload and thermodynamic provenance"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary execution or quantum chemistry metadata"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert DAGNode to standard dictionary representation."""
        return self.model_dump()

    def to_prov_jsonld(self, base_uri: str = "urn:cochem:conformer:") -> Dict[str, Any]:
        """Construct W3C PROV-O compliant JSON-LD document with offline context resolution [D].

        Args:
            base_uri: Uniform Resource Name prefix for node resolution.

        Returns:
            Dict[str, Any]: Validated JSON-LD semantic dictionary.
        """
        ctx_doc = get_local_prov_context()
        doc: Dict[str, Any] = {
            "@context": ctx_doc.get("@context", {}),
            "@id": f"{base_uri}{self.node_id}",
        }

        if self.node_type == "activity":
            types = ["prov:Activity"]
            if self.activity_type:
                types.append(self.activity_type)
            else:
                types.append("cochem:Optimization")
            doc["@type"] = types
        elif self.node_type == "agent":
            doc["@type"] = ["prov:Agent", "cochem:SoftwareAgent"]
        else:
            doc["@type"] = ["prov:Entity", "cochem:Conformer"]

        if self.parents:
            doc["prov:wasDerivedFrom"] = [{"@id": f"{base_uri}{parent_id}"} for parent_id in self.parents]

        if self.activity:
            doc["prov:wasGeneratedBy"] = {"@id": f"urn:cochem:activity:{self.activity}"}

        if self.started_at_time:
            doc["prov:startedAtTime"] = self.started_at_time
        if self.ended_at_time:
            doc["prov:endedAtTime"] = self.ended_at_time

        if self.relative_energy_kcal_mol is not None:
            doc["cochem:relativeEnergy"] = float(self.relative_energy_kcal_mol)

        if self.rotational_constants_mhz is not None:
            doc["cochem:rotationalConstants"] = [float(rc) for rc in self.rotational_constants_mhz]

        for k, v in self.metadata.items():
            doc[f"cochem:{k}"] = v

        return doc


def compute_boltzmann_weights(
    free_energies_kcal_mol: Sequence[float],
    temperature_k: float = 298.15,
    low_freq_cutoff_cm1: float = 100.0,
    damping_model: str = "grimme_quasi_rrho",
    pressure_atm: float = 1.0,
    dag_node: Optional[Any] = None,
) -> Tuple[List[float], ThermodynamicsProvenance]:
    """Computes normalized Boltzmann weights while recording thermodynamic provenance.

    Weights: w_i = exp(-Delta G_i / (R * T)) / sum(exp(-Delta G_j / (R * T)))
    Logs ThermodynamicsProvenance into dag_node.payload['thermodynamics_provenance'] if provided.
    """
    R_KCAL_MOL_K: float = 0.00198720425864083

    G = np.asarray(free_energies_kcal_mol, dtype=np.float64)
    if len(G) == 0:
        return [], ThermodynamicsProvenance(
            damping_model=damping_model,
            low_freq_cutoff_cm1=float(low_freq_cutoff_cm1),
            temperature_k=float(temperature_k),
            pressure_atm=float(pressure_atm),
            provenance_tag="[D]",
        )

    delta_G = G - np.min(G)
    beta = 1.0 / (R_KCAL_MOL_K * temperature_k)
    unnorm_weights = np.exp(-beta * delta_G)
    weights = (unnorm_weights / np.sum(unnorm_weights)).tolist()

    prov = ThermodynamicsProvenance(
        damping_model=damping_model,
        low_freq_cutoff_cm1=float(low_freq_cutoff_cm1),
        temperature_k=float(temperature_k),
        pressure_atm=float(pressure_atm),
        provenance_tag="[D]",
    )

    if dag_node is not None:
        if hasattr(dag_node, "payload") and isinstance(dag_node.payload, dict):
            dag_node.payload["thermodynamics_provenance"] = prov.model_dump(mode="json")
        elif hasattr(dag_node, "metadata") and isinstance(dag_node.metadata, dict):
            dag_node.metadata["thermodynamics_provenance"] = prov.model_dump(mode="json")

    return weights, prov


__all__ = [
    "DAGNode",
    "get_local_prov_context",
    "ThermodynamicsProvenance",
    "compute_boltzmann_weights",
]
