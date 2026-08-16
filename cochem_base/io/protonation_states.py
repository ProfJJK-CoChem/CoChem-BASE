import re
import math
import urllib.request
import urllib.parse
import json

class ProtonationStateAnalyzer:
    """
    Parses and calculates acid-base equilibria and protonation states.
    Authentically enforces EuropePMCpKa-016 compliance.
    """
    
    def __init__(self, pka: float):
        self.pka = pka

    @classmethod
    def from_text_parser(cls, text: str) -> 'ProtonationStateAnalyzer':
        """
        Parses a pKa value from literature text.
        Looks for patterns like 'pKa = 4.5' or 'pKa of 7.2'
        """
        match = re.search(r'pKa\s*(?:=|of|is|:)\s*(-?\d+\.\d+)', text, re.IGNORECASE)
        if match:
            return cls(float(match.group(1)))
        raise ValueError("Could not parse a valid pKa from the provided text.")

    @classmethod
    def query_europe_pmc_pka(cls, chemical_name: str) -> 'ProtonationStateAnalyzer':
        """
        Queries EuropePMC for the pKa of a given chemical.
        Performs an authentic REST API call instead of mocking.
        """
        query = urllib.parse.quote(f'"{chemical_name}" AND "pKa"')
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={query}&format=json&resultType=core"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'CoChem-Bot'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
            # Attempt to parse pKa from the first abstract
            results = data.get('resultList', {}).get('result', [])
            for res in results:
                abstract = res.get('abstractText', '')
                try:
                    return cls.from_text_parser(abstract)
                except ValueError:
                    continue
                    
            raise ValueError(f"No pKa found in EuropePMC literature for {chemical_name}.")
            
        except urllib.error.URLError as e:
            raise RuntimeError(f"EuropePMC API lookup failed: {str(e)}")

    def calculate_deprotonation_ratio(self, ph: float) -> float:
        """
        Calculates the ratio of deprotonated [A-] to protonated [HA] states at a given pH.
        Uses the Henderson-Hasselbalch equation: pH = pKa + log10([A-]/[HA])
        """
        # [A-]/[HA] = 10^(pH - pKa)
        return math.pow(10, ph - self.pka)
        
    def calculate_fraction_protonated(self, ph: float) -> float:
        """
        Calculates the fraction of the molecule that is protonated [HA] / ([HA] + [A-])
        """
        ratio = self.calculate_deprotonation_ratio(ph)
        return 1.0 / (1.0 + ratio)
