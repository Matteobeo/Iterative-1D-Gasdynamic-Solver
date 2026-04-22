"""
Isentropic flow relations for ideal gas.
All ratios are static/stagnation (e.g., T/T0, P/P0).
"""

import numpy as np
from scipy.optimize import brentq


def temperature_ratio(M: float, gamma: float) -> float:
    """T/T0 = (1 + (gamma-1)/2 * M^2)^(-1)"""
    return (1.0 + (gamma - 1.0) / 2.0 * M ** 2) ** (-1.0)


def pressure_ratio(M: float, gamma: float) -> float:
    """P/P0 = (1 + (gamma-1)/2 * M^2)^(-gamma/(gamma-1))"""
    return (1.0 + (gamma - 1.0) / 2.0 * M ** 2) ** (-gamma / (gamma - 1.0))


def density_ratio(M: float, gamma: float) -> float:
    """rho/rho0 = (1 + (gamma-1)/2 * M^2)^(-1/(gamma-1))"""
    return (1.0 + (gamma - 1.0) / 2.0 * M ** 2) ** (-1.0 / (gamma - 1.0))


def area_mach_ratio(M: float, gamma: float) -> float:
    """A/A* from Mach number.
    A/A* = (1/M)*[(2/(gamma+1))*(1+(gamma-1)/2*M^2)]^((gamma+1)/(2*(gamma-1)))
    """
    if abs(M) < 1e-12:
        return float("inf")
    gp1 = gamma + 1.0
    gm1 = gamma - 1.0
    term = (2.0 / gp1) * (1.0 + gm1 / 2.0 * M ** 2)
    exponent = gp1 / (2.0 * gm1)
    return (1.0 / M) * term ** exponent


def mach_from_area_ratio(A_ratio: float, gamma: float, subsonic: bool = True) -> float:
    """Invert A/A* -> M using Brent's method.

    Args:
        A_ratio: Area ratio A/A* (must be >= 1.0).
        gamma: Ratio of specific heats.
        subsonic: If True, return subsonic solution; else supersonic.

    Returns:
        Mach number.
    """
    if A_ratio < 1.0 - 1e-9:
        raise ValueError(f"Area ratio A/A* must be >= 1.0, got {A_ratio:.6f}")
    if abs(A_ratio - 1.0) < 1e-9:
        return 1.0

    def equation(M):
        return area_mach_ratio(M, gamma) - A_ratio

    if subsonic:
        # If A_ratio is very large, the Mach number is very small
        if A_ratio > 1e8:
            return 1.0 / A_ratio # Rough asymptotic approximation for M << 1
        return brentq(equation, 1e-12, 1.0 - 1e-10, xtol=1e-14)
    else:
        # Upper bound: for very large area ratios we need a high M
        M_upper = 2.0
        while equation(M_upper) < 0:
            M_upper *= 2.0
            if M_upper > 100:
                break
        return brentq(equation, 1.0 + 1e-10, M_upper, xtol=1e-12)


def mass_flow_rate(P0: float, T0: float, A: float, M: float,
                   gamma: float, R: float) -> float:
    """Compute mass flow rate from stagnation conditions.

    ṁ = P0 * A * M * sqrt(gamma/(R*T0)) * (1+(gamma-1)/2*M^2)^(-(gamma+1)/(2*(gamma-1)))
    """
    gp1 = gamma + 1.0
    gm1 = gamma - 1.0
    term = 1.0 + gm1 / 2.0 * M ** 2
    exponent = -gp1 / (2.0 * gm1)
    
    if T0 < 1e-6:
        return 0.0
        
    return P0 * A * M * np.sqrt(gamma / (R * T0)) * term ** exponent


def choked_mass_flow(P0: float, T0: float, A_star: float,
                     gamma: float, R: float) -> float:
    """Maximum (choked) mass flow rate through throat area A*."""
    return mass_flow_rate(P0, T0, A_star, 1.0, gamma, R)


def mach_from_mass_flow(mdot: float, P0: float, T0: float, A: float,
                        gamma: float, R: float, subsonic: bool = True) -> float:
    """Find Mach number given mass flow rate and stagnation conditions.

    Uses the area-Mach relation: first compute A/A* from ṁ, then invert.
    """
    mdot_max = choked_mass_flow(P0, T0, A, gamma, R)
    if mdot > mdot_max * (1.0 + 1e-9):
        raise ValueError(
            f"Mass flow {mdot:.4f} exceeds choked value {mdot_max:.4f} for area {A:.6f}"
        )
    if abs(mdot - mdot_max) / mdot_max < 1e-9:
        return 1.0

    # A* = ṁ / (P0 * sqrt(gamma/(R*T0)) * (2/(gamma+1))^((gamma+1)/(2*(gamma-1))))
    gp1 = gamma + 1.0
    gm1 = gamma - 1.0
    
    if T0 < 1e-6 or P0 < 1e-6:
        return 0.0 if mdot < 1e-12 else float("inf")

    A_star = mdot / (
        P0 * np.sqrt(gamma / (R * T0)) * (2.0 / gp1) ** (gp1 / (2.0 * gm1))
    )
    A_ratio = A / A_star
    return mach_from_area_ratio(A_ratio, gamma, subsonic=subsonic)


def static_from_stagnation(M: float, P0: float, T0: float,
                           gamma: float, R: float) -> dict:
    """Compute all static properties from Mach and stagnation conditions."""
    T = T0 * temperature_ratio(M, gamma)
    P = P0 * pressure_ratio(M, gamma)
    rho = P / (R * T) if T > 0 else 0.0
    a = np.sqrt(gamma * R * T) if T > 0 else 0.0
    V = M * a
    return {"T": T, "P": P, "rho": rho, "a": a, "V": V}
