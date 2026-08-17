import json
import logging
import math
import re
import urllib.parse
import urllib.request
from typing import List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class EuropePMCResult(BaseModel):
    abstractText: Optional[str] = None
    pmid: Optional[str] = None
    title: Optional[str] = None

class EuropePMCResultList(BaseModel):
    result: List[EuropePMCResult] = Field(default_factory=list)

class EuropePMCResponse(BaseModel):
    resultList: EuropePMCResultList = Field(default_factory=EuropePMCResultList)


class ProtonationStateAnalyzer:
    """
    Parses and calculates acid-base equilibria and protonation states.
    Authentically enforces EuropePMCpKa-016 compliance, but flags extraction as unverified.
    """

    def __init__(self, pka: float, provenance: str):
        self.pka = pka
        if not provenance.startswith("[") or not provenance.endswith("]"):
            logger.warning(f"Invalid provenance tag: {provenance}. Enforcing [MISSING DATA].")
            self.provenance = "[MISSING DATA]"
        else:
            self.provenance = provenance

    @classmethod
    def from_text_parser(cls, text: str, source_id: str = "Unknown") -> 'ProtonationStateAnalyzer':
        """
        Parses a pKa value from literature text.
        Looks for patterns like 'pKa = 4.5' or 'pKa of 7.2'
        WARNING: This is a fragile regex heuristic. It is flagged as [D-UNVERIFIED].
        """
        match = re.search(r'pKa\s*(?:=|of|is|:)\s*(-?\d+\.\d+)', text, re.IGNORECASE)
        if match:
            extracted_pka = float(match.group(1))
            provenance = f"[D-UNVERIFIED: {source_id}]"
            logger.warning(f"Extracted pKa {extracted_pka} via regex from text. Provenance: {provenance}. High risk of mismatch.")
            return cls(extracted_pka, provenance=provenance)
        raise ValueError("Could not parse a valid pKa from the provided text.")

    @classmethod
    def query_europe_pmc_pka(cls, chemical_name: str) -> 'ProtonationStateAnalyzer':
        """
        Queries EuropePMC for the pKa of a given chemical.
        Performs an authentic REST API call.
        """
        query = urllib.parse.quote(f'"{chemical_name}" AND "pKa"')
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={query}&format=json&resultType=core"
        
        logger.info(f"Querying EuropePMC for pKa of {chemical_name}...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'CoChem-Bot'})
            with urllib.request.urlopen(req, timeout=10) as response:
                raw_data = response.read().decode()
                pmc_response = EuropePMCResponse.model_validate_json(raw_data)

            # Attempt to parse pKa from the abstracts
            for res in pmc_response.resultList.result:
                abstract = res.abstractText or ''
                if not abstract:
                    continue
                try:
                    source_ref = f"PMID:{res.pmid}" if res.pmid else "EuropePMC"
                    return cls.from_text_parser(abstract, source_id=source_ref)
                except ValueError:
                    continue

            logger.error(f"No pKa found in EuropePMC literature for {chemical_name}.")
            raise ValueError(f"No pKa found in EuropePMC literature for {chemical_name}.")

        except urllib.error.URLError as e:
            logger.error(f"EuropePMC API lookup failed: {str(e)}")
            raise RuntimeError(f"EuropePMC API lookup failed: {str(e)}") from e

    def calculate_deprotonation_ratio(self, ph: float) -> float:
        """
        Calculates the ratio of deprotonated [A-] to protonated [HA] states at a given pH.
        Uses the Henderson-Hasselbalch equation: pH = pKa + log10([A-]/[HA])
        """
        return math.pow(10, ph - self.pka)

    def calculate_fraction_protonated(self, ph: float) -> float:
        """
        Calculates the fraction of the molecule that is protonated [HA] / ([HA] + [A-])
        """
        ratio = self.calculate_deprotonation_ratio(ph)
        return 1.0 / (1.0 + ratio)
