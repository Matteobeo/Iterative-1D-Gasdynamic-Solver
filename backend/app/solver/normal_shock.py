"""
Normal shock relations for ideal gas.

A normal shock is an irreversible, adiabatic discontinuity.
- T0 is preserved across the shock
- P0 decreases (entropy increase)
- Flow goes from supersonic (M1 > 1) to subsonic (M2 < 1)
"""

import numpy as np


def downstream_mach(M1: float, gamma: float) -> float:
    """Mach number downstream of normal shock.

    M2^2 = [(gamma-1)*M1^2 + 2] / [2*gamma*M1^2 - (gamma-1)]
    """
    if M1 < 1.0 - 1e-9:
        raise ValueError(f"Normal shock requires M1 >= 1.0, got {M1:.6f}")
    gp1 = gamma + 1.0
    gm1 = gamma - 1.0
    M1_sq = M1 ** 2
    M2_sq = (gm1 * M1_sq + 2.0) / (2.0 * gamma * M1_sq - gm1)
    return np.sqrt(max(M2_sq, 0.0))


def pressure_ratio(M1: float, gamma: float) -> float:
    """Static pressure ratio P2/P1 across normal shock.

    P2/P1 = 1 + 2*gamma/(gamma+1) * (M1^2 - 1)
    """
    return 1.0 + 2.0 * gamma / (gamma + 1.0) * (M1 ** 2 - 1.0)


def temperature_ratio(M1: float, gamma: float) -> float:
    """Static temperature ratio T2/T1 across normal shock.

    T2/T1 = (P2/P1) * (2 + (gamma-1)*M1^2) / ((gamma+1)*M1^2)
    """
    P_ratio = pressure_ratio(M1, gamma)
    gm1 = gamma - 1.0
    gp1 = gamma + 1.0
    return P_ratio * (2.0 + gm1 * M1 ** 2) / (gp1 * M1 ** 2)


def density_ratio(M1: float, gamma: float) -> float:
    """Density ratio rho2/rho1 across normal shock.

    rho2/rho1 = (gamma+1)*M1^2 / (2 + (gamma-1)*M1^2)
    """
    gp1 = gamma + 1.0
    gm1 = gamma - 1.0
    return gp1 * M1 ** 2 / (2.0 + gm1 * M1 ** 2)


def total_pressure_ratio(M1: float, gamma: float) -> float:
    """Total pressure ratio P02/P01 across normal shock.

    P02/P01 = [(gamma+1)*M1^2 / (2+(gamma-1)*M1^2)]^(gamma/(gamma-1)) *
              [(gamma+1) / (2*gamma*M1^2 - (gamma-1))]^(1/(gamma-1))
    """
    gp1 = gamma + 1.0
    gm1 = gamma - 1.0
    M1_sq = M1 ** 2

    term1 = (gp1 * M1_sq / (2.0 + gm1 * M1_sq)) ** (gamma / gm1)
    term2 = (gp1 / (2.0 * gamma * M1_sq - gm1)) ** (1.0 / gm1)
    return term1 * term2


def shock_relations(M1: float, gamma: float) -> dict:
    """Compute all properties across a normal shock.

    Args:
        M1: Upstream (supersonic) Mach number.
        gamma: Ratio of specific heats.

    Returns:
        dict with M2, P2/P1, T2/T1, rho2/rho1, P02/P01.
    """
    return {
        "M2": downstream_mach(M1, gamma),
        "P_ratio": pressure_ratio(M1, gamma),
        "T_ratio": temperature_ratio(M1, gamma),
        "rho_ratio": density_ratio(M1, gamma),
        "P0_ratio": total_pressure_ratio(M1, gamma),
    }
