"""
Fanno flow relations (adiabatic flow with friction in constant-area duct).

In Fanno flow:
- T0 is constant (adiabatic)
- P0 decreases (irreversible friction)
- Area is constant
- Flow is driven toward M=1 (choking)

All ratios are referenced to sonic (starred *) conditions.
"""

import numpy as np
from scipy.optimize import brentq
from app.solver.normal_shock import shock_relations


def fanno_parameter(M: float, gamma: float) -> float:
    """Compute 4fL*/D (friction parameter from M to choking).

    4fL*/D = (1-M^2)/(gamma*M^2) + (gamma+1)/(2*gamma) *
             ln[(gamma+1)*M^2 / (2 + (gamma-1)*M^2)]
    """
    if abs(M) < 1e-12:
        return float("inf")
    if abs(M - 1.0) < 1e-12:
        return 0.0

    gp1 = gamma + 1.0
    gm1 = gamma - 1.0
    M2 = M ** 2

    term1 = (1.0 - M2) / (gamma * M2)
    term2 = (gp1 / (2.0 * gamma)) * np.log(gp1 * M2 / (2.0 + gm1 * M2))
    return term1 + term2


def fanno_temperature_ratio(M: float, gamma: float) -> float:
    """T/T* = (gamma+1) / (2*(1 + (gamma-1)/2 * M^2))"""
    return (gamma + 1.0) / (2.0 * (1.0 + (gamma - 1.0) / 2.0 * M ** 2))


def fanno_pressure_ratio(M: float, gamma: float) -> float:
    """P/P* = (1/M) * sqrt((gamma+1) / (2*(1 + (gamma-1)/2 * M^2)))"""
    if abs(M) < 1e-12:
        return float("inf")
    return (1.0 / M) * np.sqrt(
        (gamma + 1.0) / (2.0 * (1.0 + (gamma - 1.0) / 2.0 * M ** 2))
    )


def fanno_total_pressure_ratio(M: float, gamma: float) -> float:
    """P0/P0* = (1/M)*[(2/(gamma+1))*(1+(gamma-1)/2*M^2)]^((gamma+1)/(2*(gamma-1)))"""
    if abs(M) < 1e-12:
        return float("inf")
    gp1 = gamma + 1.0
    gm1 = gamma - 1.0
    term = (2.0 / gp1) * (1.0 + gm1 / 2.0 * M ** 2)
    exponent = gp1 / (2.0 * gm1)
    return (1.0 / M) * term ** exponent


def fanno_velocity_ratio(M: float, gamma: float) -> float:
    """V/V* = M * sqrt((gamma+1) / (2*(1 + (gamma-1)/2 * M^2)))"""
    return M * np.sqrt(
        (gamma + 1.0) / (2.0 * (1.0 + (gamma - 1.0) / 2.0 * M ** 2))
    )


def mach_from_fanno_parameter(fLstar_D: float, gamma: float,
                               subsonic: bool = True) -> float:
    """Invert 4fL*/D -> M using root finding.

    Args:
        fLstar_D: Value of 4fL*/D (must be >= 0).
        gamma: Ratio of specific heats.
        subsonic: If True, return subsonic root; else supersonic.

    Returns:
        Mach number.
    """
    if fLstar_D < -1e-9:
        raise ValueError(f"4fL*/D must be >= 0, got {fLstar_D:.6f}")
    if abs(fLstar_D) < 1e-9:
        return 1.0

    def equation(M):
        return fanno_parameter(M, gamma) - fLstar_D

    if subsonic:
        # A/A* (or 4fL*/D) is strictly decreasing for subsonic flow.
        # Check boundaries explicitly to avoid brentq ValueError
        val_lo = equation(1e-12)
        val_hi = equation(1.0 - 1e-12)
        if val_lo <= 0: return 1e-12
        if val_hi >= 0: return 1.0
        return brentq(equation, 1e-12, 1.0 - 1e-12, xtol=1e-14)
    else:
        # Supersonic flow: 4fL*/D increases with M
        M_upper = 2.0
        while equation(M_upper) < 0 and M_upper < 100:
            M_upper *= 2.0
        val_lo = equation(1.0 + 1e-12)
        val_hi = equation(M_upper)
        if val_lo >= 0: return 1.0
        if val_hi <= 0: return M_upper
        return brentq(equation, 1.0 + 1e-12, M_upper, xtol=1e-12)


def solve_fanno(M_in: float, f: float, L: float, D_h: float,
                gamma: float) -> dict:
    """Solve Fanno flow: given inlet Mach and duct parameters, find outlet Mach.

    Args:
        M_in: Inlet Mach number.
        f: Fanning friction factor.
        L: Duct length [m].
        D_h: Hydraulic diameter [m].
        gamma: Ratio of specific heats.

    Returns:
        dict with M_out, choked flag, and ratios.
    """
    # 4fL/D for this duct
    fLD = 4.0 * f * L / D_h

    # Remaining length to choking at inlet
    fLstar_in = fanno_parameter(M_in, gamma)

    # Remaining length to choking at outlet
    fLstar_out = fLstar_in - fLD

    choked = False
    if fLstar_out < -1e-9:
        # Flow would need to choke before reaching the exit
        choked = True
        fLstar_out = 0.0

    is_subsonic = M_in < 1.0
    M_out = mach_from_fanno_parameter(max(fLstar_out, 0.0), gamma,
                                       subsonic=is_subsonic)

    # Compute property changes across the duct
    # P_out/P_in = (P/P*)_out / (P/P*)_in
    P_ratio = fanno_pressure_ratio(M_out, gamma) / fanno_pressure_ratio(M_in, gamma)
    T_ratio = fanno_temperature_ratio(M_out, gamma) / fanno_temperature_ratio(M_in, gamma)
    P0_ratio = fanno_total_pressure_ratio(M_out, gamma) / fanno_total_pressure_ratio(M_in, gamma)

    return {
        "M_out": M_out,
        "choked": choked,
        "P_ratio": P_ratio,      # P_out / P_in
        "T_ratio": T_ratio,      # T_out / T_in
        "P0_ratio": P0_ratio,    # P0_out / P0_in (< 1, total pressure loss)
        "fLD": fLD,
        "fLstar_in": fLstar_in,
        "fLstar_out": max(fLstar_out, 0.0),
    }


def find_fanno_shock_mach(M_in: float, fLD_total: float, gamma: float, target_P_out_ratio: float = None) -> float:
    """
    Finds the upstream shock Mach number M_x_u for a supersonic Fanno flow
    that must either:
      1) exit exactly at M=1 (target_P_out_ratio = None) -> Long Duct case
      2) match a specific exit pressure ratio (P_out / P_in) -> Short Duct with high backpressure

    Returns M_x_u.
    """
    fLstar_in = fanno_parameter(M_in, gamma)

    def obj_critical(M_xu):
        # M_xu is the guess for the Mach number just upstream of the shock
        # Length from inlet to shock:
        fL_x = fLstar_in - fanno_parameter(M_xu, gamma)
        
        # Shock relations:
        rel = shock_relations(M_xu, gamma)
        M_xd = rel["M2"]
        
        # Length from shock to exit:
        fL_x3 = fLD_total - fL_x
        
        # We want the flow to exactly reach M=1 at the exit:
        # So fLstar(M_xd) must equal the remaining length fL_x3
        fLstar_xd = fanno_parameter(M_xd, gamma)
        return fLstar_xd - fL_x3

    def obj_pressure(M_xu):
        # Length from inlet to shock:
        fL_x = fLstar_in - fanno_parameter(M_xu, gamma)
        
        # Shock relations:
        rel = shock_relations(M_xu, gamma)
        M_xd = rel["M2"]
        P_ratio_shock = rel["P_ratio"]
        
        # Remaining length:
        fL_x3 = fLD_total - fL_x
        
        # Subsonic flow to exit:
        fLstar_xd = fanno_parameter(M_xd, gamma)
        fLstar_out = fLstar_xd - fL_x3
        
        if fLstar_out < 0:
            return -1e6 # Flow choked downstream, invalid M_xu

        M_out = mach_from_fanno_parameter(fLstar_out, gamma, subsonic=True)
        
        # P_out / P_in = (P_xu / P_in) * (P_xd / P_xu) * (P_out / P_xd)
        P_xu_ratio = fanno_pressure_ratio(M_xu, gamma) / fanno_pressure_ratio(M_in, gamma)
        P_out_xd_ratio = fanno_pressure_ratio(M_out, gamma) / fanno_pressure_ratio(M_xd, gamma)
        
        current_P_out_ratio = P_xu_ratio * P_ratio_shock * P_out_xd_ratio
        return current_P_out_ratio - target_P_out_ratio

    # The shock can be anywhere from the inlet (M_xu = M_in) to the theoretical choking point.
    # The minimum M_xu is 1.0 (shock right at the choking point), but actually M_xu must be > 1.
    M_xu_min = 1.0 + 1e-6
    # If the duct is shorter than fLstar_in, the shock can be at the exit where M_xu is M_exit_supersonic
    if fLD_total < fLstar_in:
        M_xu_min = mach_from_fanno_parameter(fLstar_in - fLD_total, gamma, subsonic=False)
        
    M_xu_max = M_in

    # If target is None, we find the critical shock position (M3 = 1)
    if target_P_out_ratio is None:
        try:
            return brentq(obj_critical, M_xu_min, M_xu_max)
        except ValueError:
            raise RuntimeError("Could not find critical internal shock Mach number.")
    else:
        try:
            return brentq(obj_pressure, M_xu_min, M_xu_max)
        except ValueError:
            raise RuntimeError("Could not match Fanno internal shock to backpressure.")
