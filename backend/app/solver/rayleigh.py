"""
Rayleigh flow relations (frictionless flow with heat transfer in constant-area duct).

In Rayleigh flow:
- Area is constant, no friction
- Heat addition drives subsonic flow toward M=1 (thermal choking)
- Heat removal drives flow away from M=1

All ratios are referenced to sonic (starred *) conditions.
"""

import numpy as np
from scipy.optimize import brentq


def rayleigh_total_temperature_ratio(M: float, gamma: float) -> float:
    """T0/T0* = 2*(gamma+1)*M^2 / (1+gamma*M^2)^2 * (1 + (gamma-1)/2 * M^2)"""
    gp1 = gamma + 1.0
    gm1 = gamma - 1.0
    M2 = M ** 2
    return 2.0 * gp1 * M2 / (1.0 + gamma * M2) ** 2 * (1.0 + gm1 / 2.0 * M2)


def rayleigh_temperature_ratio(M: float, gamma: float) -> float:
    """T/T* = [M*(gamma+1) / (1 + gamma*M^2)]^2"""
    M2 = M ** 2
    return (M * (gamma + 1.0) / (1.0 + gamma * M2)) ** 2


def rayleigh_pressure_ratio(M: float, gamma: float) -> float:
    """P/P* = (gamma+1) / (1 + gamma*M^2)"""
    return (gamma + 1.0) / (1.0 + gamma * M ** 2)


def rayleigh_total_pressure_ratio(M: float, gamma: float) -> float:
    """P0/P0* = [(gamma+1)/(1+gamma*M^2)] *
               [(2/(gamma+1))*(1+(gamma-1)/2*M^2)]^(gamma/(gamma-1))
    """
    gp1 = gamma + 1.0
    gm1 = gamma - 1.0
    M2 = M ** 2
    term1 = gp1 / (1.0 + gamma * M2)
    term2 = (2.0 / gp1) * (1.0 + gm1 / 2.0 * M2)
    return term1 * term2 ** (gamma / gm1)


def rayleigh_velocity_ratio(M: float, gamma: float) -> float:
    """V/V* = (gamma+1)*M^2 / (1 + gamma*M^2)"""
    return (gamma + 1.0) * M ** 2 / (1.0 + gamma * M ** 2)


def mach_from_rayleigh_T0_ratio(T0_ratio: float, gamma: float,
                                 subsonic: bool = True) -> float:
    """Invert T0/T0* -> M using exact quadratic solution.

    Args:
        T0_ratio: Value of T0/T0* (must be in [0, 1]).
        gamma: Ratio of specific heats.
        subsonic: If True, return subsonic root; else supersonic.

    Returns:
        Mach number.
    """
    if T0_ratio > 1.0 + 1e-9:
        raise ValueError(f"T0/T0* must be <= 1.0, got {T0_ratio:.6f}")
    
    tau = max(0.0, min(T0_ratio, 1.0))
    if tau < 1e-9:
        return 0.0
    if abs(tau - 1.0) < 1e-9:
        return 1.0

    if not subsonic:
        tau_min = (gamma**2 - 1.0) / gamma**2
        if tau <= tau_min + 1e-9:
            return 50.0  # Asymptotic Mach limit for extreme cooling

    # Exact quadratic solution for M^2
    # (gamma^2 - 1 - tau * gamma^2) M^4 + 2(gamma+1 - tau * gamma) M^2 - tau = 0
    A = (gamma**2 - 1.0) - tau * gamma**2
    B = 2.0 * (gamma + 1.0 - tau * gamma)
    C = -tau

    if abs(A) < 1e-12:
        # Linear equation if A = 0
        M2_val = -C / B
        roots = [np.sqrt(max(0.0, M2_val))]
    else:
        Delta = B**2 - 4.0 * A * C
        if Delta < 0:
            return 1.0 # Due to numerical rounding at M=1

        M2_1 = (-B + np.sqrt(Delta)) / (2.0 * A)
        M2_2 = (-B - np.sqrt(Delta)) / (2.0 * A)

        roots = []
        if M2_1 > 0: roots.append(np.sqrt(M2_1))
        if M2_2 > 0: roots.append(np.sqrt(M2_2))

    if not roots:
        return 1.0

    if subsonic:
        valid = [r for r in roots if r <= 1.0 + 1e-6]
        return min(valid) if valid else min(roots)
    else:
        valid = [r for r in roots if r >= 1.0 - 1e-6]
        return max(valid) if valid else max(roots)


def solve_rayleigh(M_in: float, q: float, T0_in: float, cp: float,
                   gamma: float) -> dict:
    """Solve Rayleigh flow: given inlet conditions and heat, find outlet.

    Args:
        M_in: Inlet Mach number.
        q: Heat added per unit mass [J/kg]. Positive = heating, negative = cooling.
        T0_in: Inlet stagnation temperature [K].
        cp: Specific heat at constant pressure [J/(kg·K)].
        gamma: Ratio of specific heats.

    Returns:
        dict with M_out, T0_out, choked flag, and ratios.
    """
    # Energy equation: T0_out = T0_in + q / cp
    T0_out = T0_in + q / cp

    if T0_out <= 0:
        raise ValueError(f"Heat removal too large: T0_out = {T0_out:.1f} K <= 0")

    # Reference to sonic conditions
    t0_ratio_in = rayleigh_total_temperature_ratio(M_in, gamma)
    if t0_ratio_in < 1e-12:
        # For M -> 0, T0_star goes to infinity. 
        # We handle this by setting a very small T0_out_ratio.
        T0_out_ratio = 1e-12 
    else:
        T0_star = T0_in / t0_ratio_in
        T0_out_ratio = T0_out / T0_star

    choked = False
    if T0_out_ratio > 1.0 + 1e-9:
        # Thermal choking — too much heat
        choked = True
        T0_out_ratio = 1.0
        T0_out = T0_star  # Adjust to choked condition

    is_subsonic = M_in < 1.0
    M_out = mach_from_rayleigh_T0_ratio(min(T0_out_ratio, 1.0), gamma,
                                         subsonic=is_subsonic)

    # Property ratios across the component
    P_ratio = rayleigh_pressure_ratio(M_out, gamma) / rayleigh_pressure_ratio(M_in, gamma)
    T_ratio = rayleigh_temperature_ratio(M_out, gamma) / rayleigh_temperature_ratio(M_in, gamma)
    P0_ratio = rayleigh_total_pressure_ratio(M_out, gamma) / rayleigh_total_pressure_ratio(M_in, gamma)

    return {
        "M_out": M_out,
        "T0_out": T0_out,
        "choked": choked,
        "P_ratio": P_ratio,
        "T_ratio": T_ratio,
        "P0_ratio": P0_ratio,
        "T0_ratio": T0_out / T0_in,
    }
