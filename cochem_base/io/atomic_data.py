"""
atomic_data.py - PubChem-compatible atomic data and isotopic validation hooks.
"""

class PubChemAtomicDataValidator:
    def __init__(self):
        # Known elemental stable/common isotopes and their approximate isotopic masses
        self.known_isotopes = {
            "H": {1: 1.007825, 2: 2.014102, 3: 3.016049},
            "He": {3: 3.016029, 4: 4.002603},
            "Li": {6: 6.015122, 7: 7.016004},
            "C": {12: 12.000000, 13: 13.003355, 14: 14.003241},
            "N": {14: 14.003074, 15: 15.000108},
            "O": {16: 15.994915, 17: 16.999131, 18: 17.999160},
            "F": {19: 18.998403},
            "Ne": {20: 19.992440, 21: 20.993846, 22: 21.991385},
            "Na": {23: 22.989769},
            "Mg": {24: 23.985041, 25: 24.985836, 26: 25.982592},
            "Al": {27: 26.981538},
            "Si": {28: 27.976926, 29: 28.976494, 30: 29.973770},
            "P": {31: 30.973761},
            "S": {32: 31.972071, 33: 32.971458, 34: 33.967866, 36: 35.967080},
            "Cl": {35: 34.968852, 37: 36.965902},
            "Ar": {36: 35.967545, 38: 37.962732, 40: 39.962383},
            "K": {39: 38.963706, 40: 39.963998, 41: 40.961825},
            "Ca": {40: 39.962590, 42: 41.958618, 43: 42.958766, 44: 43.955481, 46: 45.953692, 48: 47.952522},
        }
        
    def validate_isotopic_mass(self, element: str, mass_number: int, mass: float, tolerance: float = 0.05) -> bool:
        """
        Validates if the provided isotopic mass is physically reasonable and matches 
        known PubChem isotopic masses within a given tolerance.
        """
        if not isinstance(mass, (int, float)):
            raise TypeError("Mass must be a numeric value.")
            
        if mass <= 0:
            raise ValueError(f"Isotopic mass must be positive, got {mass}")
            
        if mass > 300:
            raise ValueError(f"Isotopic mass is unreasonably large: {mass}")

        if element not in self.known_isotopes:
            if abs(mass - mass_number) > 1.0:
                raise ValueError(f"Mass {mass} deviates too much from mass number {mass_number} for unknown element {element}.")
            return True
            
        element_data = self.known_isotopes[element]
        if mass_number not in element_data:
            raise ValueError(f"Unknown isotope: {element}-{mass_number}")
            
        expected_mass = element_data[mass_number]
        
        if abs(mass - expected_mass) > tolerance:
            raise ValueError(
                f"Isotopic mass {mass} for {element}-{mass_number} deviates from expected {expected_mass} "
                f"by more than {tolerance}."
            )
            
        return True

def validate_isotopic_mass(element: str, mass_number: int, mass: float) -> bool:
    """
    Hook function for PubChem validation.
    """
    validator = PubChemAtomicDataValidator()
    return validator.validate_isotopic_mass(element, mass_number, mass)
