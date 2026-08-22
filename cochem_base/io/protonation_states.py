"""Acid-base equilibria, protonation state distributions, and EuropePMC pKa extraction.

Implements Henderson-Hasselbalch equations, polyprotic alpha-distribution solvers,
isoelectric point (pI) derivation, Van Slyke buffer capacity calculations,
and thermodynamic free energy dissociation metrics.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

LN_10: float = 2.302585092994046
R_GAS_CONSTANT_KJ: float = 0.00831446261815324
STANDARD_TEMPERATURE_K: float = 298.15


class EuropePMCResult(BaseModel):
    id: Optional[str] = None
    source: Optional[str] = None
    pmid: Optional[str] = None
    doi: Optional[str] = None
    title: Optional[str] = None
    abstractText: Optional[str] = None


class EuropePMCResultList(BaseModel):
    result: List[EuropePMCResult] = Field(default_factory=list)


class EuropePMCResponse(BaseModel):
    version: Optional[str] = ""
    hitCount: int = 0
    resultList: EuropePMCResultList = Field(default_factory=EuropePMCResultList)


class ProtonationSpecies(BaseModel):
    index: int
    label: str
    charge: int
    fraction: float
    percentage: float


class AcidBaseEquilibrium(BaseModel):
    step: int
    pka: float
    ka: float
    delta_g_standard_kj: float
    equation: str


class TitrationPoint(BaseModel):
    ph: float
    average_protonation_number: float
    net_charge: float
    buffer_capacity: float
    species_fractions: List[float]
    dominant_species_index: int


def henderson_hasselbalch_ratio(ph: float, pka: float) -> float:
    """Calculates [A-]/[HA] ratio: 10^(pH - pKa)."""
    exponent = ph - pka
    if exponent > 100:
        return 1e100
    if exponent < -100:
        return 0.0
    return math.pow(10.0, exponent)


def fraction_protonated(ph: float, pka: float) -> float:
    """Calculates mole fraction of protonated species [HA]."""
    ratio = henderson_hasselbalch_ratio(ph, pka)
    return 1.0 / (1.0 + ratio)


def fraction_deprotonated(ph: float, pka: float) -> float:
    """Calculates mole fraction of deprotonated species [A-]."""
    ratio = henderson_hasselbalch_ratio(ph, pka)
    return ratio / (1.0 + ratio)


def calculate_polyprotic_alpha(ph: float, pka_values: Sequence[float]) -> List[float]:
    """Calculates the exact alpha mole fractions (alpha_0 to alpha_n) for an n-protic acid."""
    pkas = sorted([float(v) for v in pka_values])
    n = len(pkas)
    log_h = -ph

    # D = sum_{i=0}^n 10^( (n - i)*(-pH) - sum_{j=1}^i pKa_j )
    log_terms = []
    for i in range(n + 1):
        log_h_factor = (n - i) * log_h
        sum_pka = sum(pkas[:i])
        log_terms.append(log_h_factor - sum_pka)

    # Shift by maximum log term to prevent numerical overflow/underflow
    max_log = max(log_terms)
    scaled_terms = [math.pow(10.0, lt - max_log) for lt in log_terms]
    total_d = sum(scaled_terms)

    if total_d <= 0.0:
        alphas = [0.0] * (n + 1)
        alphas[0] = 1.0
        return alphas

    return [st / total_d for st in scaled_terms]


def calculate_isoelectric_point(
    pka_values: Sequence[float], charge_fully_protonated: int = 1
) -> float:
    """Derives the exact isoelectric point (pI) where net charge equals zero."""
    pkas = sorted([float(v) for v in pka_values])
    z0 = charge_fully_protonated
    n = len(pkas)

    # If z0 is outside [1, n], charge cannot cross zero
    if z0 <= 0 or z0 > n:
        raise ValueError("No isoelectric crossing found: net charge cannot cross zero.")

    # High-precision Brent / Bisection root finding on net charge
    def net_charge_at_ph(ph: float) -> float:
        alphas = calculate_polyprotic_alpha(ph, pkas)
        return sum(alphas[i] * (z0 - i) for i in range(n + 1))

    low = min(pkas) - 3.0
    high = max(pkas) + 3.0
    f_low = net_charge_at_ph(low)
    f_high = net_charge_at_ph(high)

    if f_low * f_high > 0:
        raise ValueError("No isoelectric crossing found across titration bounds.")

    for _ in range(100):
        mid = (low + high) / 2.0
        f_mid = net_charge_at_ph(mid)
        if abs(f_mid) < 1e-12 or (high - low) < 1e-10:
            return mid
        if f_low * f_mid <= 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid

    return (low + high) / 2.0


def parse_pka_text(text: str, source_id: str = "Unknown") -> Tuple[float, ...]:
    """Extracts pKa values from literature text using regex heuristics."""
    patterns = [
        r'pKa\s*(?:=|of|is|:|\~)\s*(-?\d+\.?\d*)',
        r'pKa\d?\s*(?:=|of|is|:|\~)\s*(-?\d+\.?\d*)',
    ]
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            try:
                found.append(float(m.group(1)))
            except ValueError:
                pass
    if not found:
        raise ValueError(f"Could not parse a valid pKa from the provided text for {source_id}.")
    return tuple(found)


class ProtonationStateAnalyzer:
    """Parses, analyzes, and calculates acid-base equilibria and protonation states."""

    def __init__(
        self,
        pka: Union[float, Sequence[float]],
        provenance: str = "[MISSING DATA]",
        charge_fully_protonated: int = 0,
        name: Optional[str] = None,
    ) -> None:
        if isinstance(pka, (int, float)):
            if math.isnan(pka) or math.isinf(pka):
                raise ValueError("Invalid pKa value: must be a finite number")
            self._pka_values = (float(pka),)
        else:
            if not pka:
                raise ValueError("At least one pKa value must be provided")
            clean_pkas = []
            for v in pka:
                if math.isnan(v) or math.isinf(v):
                    raise ValueError("Invalid pKa value: must be a finite number")
                clean_pkas.append(float(v))
            self._pka_values = tuple(sorted(clean_pkas))

        self.pka: float = self._pka_values[0]
        self.pka_values: Tuple[float, ...] = self._pka_values
        self.charge_fully_protonated: int = charge_fully_protonated
        self.name: Optional[str] = name

        if not provenance.startswith("[") or not provenance.endswith("]"):
            logger.warning("Invalid provenance tag: %s. Enforcing [MISSING DATA].", provenance)
            self.provenance = "[MISSING DATA]"
        else:
            self.provenance = provenance

    @property
    def is_polyprotic(self) -> bool:
        return len(self._pka_values) > 1

    @property
    def num_dissociation_steps(self) -> int:
        return len(self._pka_values)

    @property
    def num_species(self) -> int:
        return len(self._pka_values) + 1

    def __len__(self) -> int:
        return len(self._pka_values)

    def __getitem__(self, index: int) -> float:
        return self._pka_values[index]

    def __iter__(self) -> Iterator[float]:
        return iter(self._pka_values)

    def __repr__(self) -> str:
        if self.is_polyprotic:
            return (
                f"ProtonationStateAnalyzer(pka_values={self._pka_values}, "
                f"charge={self.charge_fully_protonated}, provenance={self.provenance!r})"
            )
        return (
            f"ProtonationStateAnalyzer(pka={self.pka:.4f}, "
            f"charge={self.charge_fully_protonated}, provenance={self.provenance!r})"
        )

    def __str__(self) -> str:
        return repr(self)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ProtonationStateAnalyzer):
            return False
        return (
            self._pka_values == other._pka_values
            and self.provenance == other.provenance
            and self.charge_fully_protonated == other.charge_fully_protonated
            and self.name == other.name
        )

    def calculate_deprotonation_ratio(self, ph: float) -> float:
        return henderson_hasselbalch_ratio(ph, self.pka)

    def calculate_fraction_protonated(self, ph: float) -> float:
        return fraction_protonated(ph, self.pka)

    def calculate_fraction_deprotonated(self, ph: float) -> float:
        return fraction_deprotonated(ph, self.pka)

    def calculate_species_fractions(self, ph: float) -> List[float]:
        return calculate_polyprotic_alpha(ph, self._pka_values)

    def calculate_average_protonation_number(self, ph: float) -> float:
        alphas = self.calculate_species_fractions(ph)
        n = self.num_dissociation_steps
        return sum(alphas[i] * (n - i) for i in range(n + 1))

    def calculate_net_charge(self, ph: float) -> float:
        alphas = self.calculate_species_fractions(ph)
        z0 = self.charge_fully_protonated
        return sum(alphas[i] * (z0 - i) for i in range(len(alphas)))

    def calculate_isoelectric_point(self) -> float:
        return calculate_isoelectric_point(self._pka_values, self.charge_fully_protonated)

    def calculate_buffer_capacity(self, ph: float, c_total: float = 0.1) -> float:
        if c_total < 0:
            raise ValueError("Total buffer concentration cannot be negative")
        alphas = self.calculate_species_fractions(ph)
        n = self.num_dissociation_steps
        h_conc = math.pow(10.0, -ph)
        oh_conc = math.pow(10.0, -(14.0 - ph))

        # Van Slyke buffer index for polyprotic system
        sum_cross = 0.0
        for i in range(n + 1):
            for j in range(i + 1, n + 1):
                sum_cross += ((j - i)**2) * alphas[i] * alphas[j]

        return LN_10 * (h_conc + oh_conc + c_total * sum_cross)

    def simulate_titration(
        self, ph_min: float = 0.0, ph_max: float = 14.0, step: float = 0.2, c_total: float = 0.1
    ) -> List[TitrationPoint]:
        if ph_min >= ph_max:
            raise ValueError(f"ph_min ({ph_min}) must be strictly less than ph_max ({ph_max})")
        if step <= 0:
            raise ValueError("Titration step must be strictly positive")

        points = []
        curr_ph = ph_min
        while curr_ph <= ph_max + 1e-9:
            alphas = self.calculate_species_fractions(curr_ph)
            n_bar = self.calculate_average_protonation_number(curr_ph)
            net_q = self.calculate_net_charge(curr_ph)
            beta = self.calculate_buffer_capacity(curr_ph, c_total=c_total)
            dom_idx = int(max(range(len(alphas)), key=lambda i: alphas[i]))

            points.append(
                TitrationPoint(
                    ph=round(curr_ph, 4),
                    average_protonation_number=n_bar,
                    net_charge=net_q,
                    buffer_capacity=beta,
                    species_fractions=alphas,
                    dominant_species_index=dom_idx,
                )
            )
            curr_ph += step
        return points

    def dissociation_constant(self, step: int) -> float:
        if step < 1 or step > len(self._pka_values):
            raise ValueError(f"Step {step} out of bounds (1 to {len(self._pka_values)})")
        return math.pow(10.0, -self._pka_values[step - 1])

    def standard_gibbs_free_energy(
        self, step: int, temperature_k: float = STANDARD_TEMPERATURE_K
    ) -> float:
        if step < 1 or step > len(self._pka_values):
            raise ValueError(f"Step {step} out of bounds (1 to {len(self._pka_values)})")
        pka_val = self._pka_values[step - 1]
        return LN_10 * R_GAS_CONSTANT_KJ * temperature_k * pka_val

    @property
    def equilibria(self) -> List[AcidBaseEquilibrium]:
        eqs = []
        for i, pka_val in enumerate(self._pka_values, 1):
            ka = math.pow(10.0, -pka_val)
            dg = LN_10 * R_GAS_CONSTANT_KJ * STANDARD_TEMPERATURE_K * pka_val
            eqs.append(
                AcidBaseEquilibrium(
                    step=i,
                    pka=pka_val,
                    ka=ka,
                    delta_g_standard_kj=dg,
                    equation=f"H_{len(self._pka_values)-i+1}A -> H_{len(self._pka_values)-i}A + H+",
                )
            )
        return eqs

    def dominant_species_index(self, ph: float) -> int:
        alphas = self.calculate_species_fractions(ph)
        return int(max(range(len(alphas)), key=lambda i: alphas[i]))

    def get_species_breakdown(
        self, ph: float, labels: Optional[List[str]] = None
    ) -> List[ProtonationSpecies]:
        alphas = self.calculate_species_fractions(ph)
        species = []
        z0 = self.charge_fully_protonated
        n = self.num_dissociation_steps

        for i, frac in enumerate(alphas):
            if labels and i < len(labels):
                lbl = labels[i]
            else:
                num_h = n - i
                lbl = f"H{num_h}A^({z0-i:+d})" if z0 - i != 0 else f"H{num_h}A"
            species.append(
                ProtonationSpecies(
                    index=i,
                    label=lbl,
                    charge=z0 - i,
                    fraction=frac,
                    percentage=frac * 100.0,
                )
            )
        return species

    def pka_summary(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "provenance": self.provenance,
            "is_polyprotic": self.is_polyprotic,
            "pka_values": list(self._pka_values),
            "charge_fully_protonated": self.charge_fully_protonated,
            "equilibria": [e.model_dump() for e in self.equilibria],
        }

    @classmethod
    def from_text_parser(
        cls, text: str, source_id: str = "Unknown"
    ) -> ProtonationStateAnalyzer:
        match = re.search(r'pKa\s*(?:=|of|is|:|\~)\s*(-?\d+\.?\d*)', text, re.IGNORECASE)
        if match:
            extracted_pka = float(match.group(1))
            provenance = f"[D-UNVERIFIED: {source_id}]"
            return cls(extracted_pka, provenance=provenance)
        raise ValueError("Could not parse a valid pKa from the provided text.")

    @classmethod
    def from_polyprotic_text(
        cls, text: str, source_id: str = "Unknown"
    ) -> ProtonationStateAnalyzer:
        matches = re.findall(r'pKa\d?\s*(?:=|of|is|:|\~)\s*(-?\d+\.?\d*)', text, re.IGNORECASE)
        if matches:
            pkas = [float(m) for m in matches]
            provenance = f"[D-UNVERIFIED: {source_id}]"
            return cls(pkas, provenance=provenance)
        raise ValueError("Could not parse any valid pKa values from the provided polyprotic text.")

    @classmethod
    def query_europe_pmc_pka(
        cls, chemical_name: str, timeout: float = 10.0
    ) -> ProtonationStateAnalyzer:
        query = urllib.parse.quote(f'"{chemical_name}" AND "pKa"')
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={query}&format=json&resultType=core"

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'CoChem-Bot'})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw_data = response.read().decode()
                pmc_response = EuropePMCResponse.model_validate_json(raw_data)

            for res in pmc_response.resultList.result:
                abstract = res.abstractText or ''
                if not abstract:
                    continue
                try:
                    source_ref = f"PMID:{res.pmid}" if res.pmid else "EuropePMC"
                    return cls.from_text_parser(abstract, source_id=source_ref)
                except ValueError:
                    continue

            raise ValueError(f"No pKa found in EuropePMC literature for {chemical_name}.")

        except urllib.error.URLError as e:
            raise RuntimeError(f"EuropePMC API lookup failed: {str(e)}") from e
        except Exception as e:
            if isinstance(e, (ValueError, RuntimeError)):
                raise
            raise RuntimeError(f"EuropePMC API lookup failed: {str(e)}") from e


__all__ = [
    "AcidBaseEquilibrium",
    "EuropePMCResponse",
    "EuropePMCResult",
    "EuropePMCResultList",
    "LN_10",
    "ProtonationSpecies",
    "ProtonationStateAnalyzer",
    "R_GAS_CONSTANT_KJ",
    "STANDARD_TEMPERATURE_K",
    "TitrationPoint",
    "calculate_isoelectric_point",
    "calculate_polyprotic_alpha",
    "fraction_deprotonated",
    "fraction_protonated",
    "henderson_hasselbalch_ratio",
    "parse_pka_text",
]
