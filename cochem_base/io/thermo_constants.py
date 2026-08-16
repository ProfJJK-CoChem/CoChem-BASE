STANDARD_TEMPERATURE = 298.15
STANDARD_PRESSURE = 100000.0

class ThermoConstantsValidator:
    """Validates thermodynamic conditions against standard states and basic physical boundaries."""

    @staticmethod
    def validate_temperature(temperature: float):
        """
        Validates the given temperature.
        Args:
            temperature: The temperature in Kelvin.
        Raises:
            ValueError: If the temperature is negative.
        """
        if temperature < 0:
            raise ValueError(f"Temperature cannot be negative. Got {temperature} K.")
        return True

    @staticmethod
    def validate_pressure(pressure: float):
        """
        Validates the given pressure.
        Args:
            pressure: The pressure in Pascals.
        Raises:
            ValueError: If the pressure is negative.
        """
        if pressure < 0:
            raise ValueError(f"Pressure cannot be negative. Got {pressure} Pa.")
        return True

    @classmethod
    def is_standard_state(cls, temperature: float, pressure: float, temp_tol: float = 0.01, press_tol: float = 1.0) -> bool:
        """
        Checks if the given temperature and pressure represent a standard state.
        
        Args:
            temperature: The temperature in Kelvin.
            pressure: The pressure in Pascals.
            temp_tol: Tolerance for temperature matching (K).
            press_tol: Tolerance for pressure matching (Pa).
            
        Returns:
            bool: True if the conditions are at standard state, False otherwise.
            
        Raises:
            ValueError: If temperature or pressure is physically invalid.
        """
        cls.validate_temperature(temperature)
        cls.validate_pressure(pressure)

        temp_match = abs(temperature - STANDARD_TEMPERATURE) <= temp_tol
        press_match = abs(pressure - STANDARD_PRESSURE) <= press_tol
        
        return temp_match and press_match
