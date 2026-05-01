"""
Gas properties for ideal gas calculations.
"""

import numpy as np


class GasProperties:
    """Ideal gas properties container."""

    def __init__(self, gamma: float = 1.4, R: float = 287.0):
        self.gamma = gamma
        self.R = R
        self.cp = gamma * R / (gamma - 1)
        self.cv = R / (gamma - 1)

    def speed_of_sound(self, T: float) -> float:
        """Speed of sound a = sqrt(gamma * R * T)."""
        return np.sqrt(self.gamma * self.R * T)

    def density(self, P: float, T: float) -> float:
        """Density from ideal gas law: rho = P / (R * T)."""
        if T < 1e-6:
            return 0.0
        return P / (self.R * T)

    def area_from_diameter(self, d: float) -> float:
        """Circular cross-section area from diameter."""
        return np.pi / 4 * d ** 2

    def diameter_from_area(self, A: float) -> float:
        """Diameter from circular cross-section area."""
        return np.sqrt(4 * A / np.pi)


class RealGasProperties(GasProperties):
    """Real gas properties container using Van der Waals EOS."""

    def __init__(self, gamma: float = 1.4, R: float = 287.0, a: float = 0.0, b: float = 0.0):
        super().__init__(gamma, R)
        self.a = a  # Van der Waals 'a' parameter
        self.b = b  # Van der Waals 'b' parameter
