import math

class SingularityError(ValueError):
    """Exception raised when a singularity is encountered in calculations."""

def coulomb_potential(q1: float, q2: float, distance: float, k: float = 8.9875517923e9) -> float:
    """
    Calculates the Coulomb potential between two point charges.
    
    Args:
        q1: Charge of the first particle in Coulombs.
        q2: Charge of the second particle in Coulombs.
        distance: Distance between the particles in meters.
        k: Coulomb's constant, default is approximately 8.9875517923e9 N m^2 C^-2.
        
    Returns:
        The Coulomb potential in Joules.
        
    Raises:
        SingularityError: If the distance is dangerously close to zero.
    """
    if distance < 1e-12:
        raise SingularityError(f"Distance {distance} is dangerously close to zero, causing a singularity.")
    
    return k * q1 * q2 / distance

def coulomb_gradient(q1: float, q2: float, dx: float, dy: float, dz: float, k: float = 8.9875517923e9):
    """
    Calculates the gradient of the Coulomb potential between two point charges.
    
    Args:
        q1: Charge of the first particle in Coulombs.
        q2: Charge of the second particle in Coulombs.
        dx, dy, dz: Components of the distance vector between the particles in meters.
        k: Coulomb's constant, default is approximately 8.9875517923e9 N m^2 C^-2.
        
    Returns:
        A tuple (fx, fy, fz) representing the force vector (negative gradient of potential).
        
    Raises:
        SingularityError: If the distance is dangerously close to zero.
    """
    distance_sq = dx**2 + dy**2 + dz**2
    distance = math.sqrt(distance_sq)
    
    if distance < 1e-12:
        raise SingularityError(f"Distance {distance} is dangerously close to zero, causing a singularity.")
    
    magnitude = k * q1 * q2 / (distance_sq * distance)
    return (magnitude * dx, magnitude * dy, magnitude * dz)
