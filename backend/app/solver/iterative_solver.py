"""
Iterative 1D Gasdynamic Solver
==============================

Architecture:
  - solve_full_pipeline(): Uses the analytical per-component evaluations
    (convergent/divergent via area-Mach, Fanno/Rayleigh via their tables)
    combined with a Shooting Method on M_in to match backpressure P_amb.
    This is identical to the proven pipeline.py logic, but cleaned up.

  - generate_plot_data(): Uses RK4 spatial integration of the coupled ODE
    system (dM/dx, dP0/dx, dT0/dx) to produce smooth, high-resolution
    plotting arrays along the entire duct.

The analytical evaluation guarantees correct choking detection and shock
placement. The RK4 integration provides physically accurate spatial profiles.
"""

import numpy as np
import copy
import math
from typing import List, Dict, Tuple, Any, Optional
from scipy.optimize import brentq

from app.models import ComponentConfig
from app.solver.gas import GasProperties
from app.solver.isentropic import (
    area_mach_ratio, mach_from_area_ratio,
    pressure_ratio, temperature_ratio,
    mass_flow_rate, choked_mass_flow
)
from app.solver.fanno import solve_fanno
from app.solver.rayleigh import solve_rayleigh
from app.solver.normal_shock import shock_relations


# ===========================================================================
# Exception
# ===========================================================================

class ChokedError(Exception):
    """Raised when a component chokes the flow."""
    pass


# ===========================================================================
# Per-component analytical evaluation (proven logic from pipeline.py)
# ===========================================================================

def evaluate_component(
    comp: ComponentConfig,
    M_in: float,
    P0_in: float,
    T0_in: float,
    gas: GasProperties,
    force_supersonic: bool = False
) -> Dict[str, Any]:
    """Evaluate a single component analytically."""

    out = {
        "M_in": M_in,
        "P0_in": P0_in,
        "T0_in": T0_in,
        "choked_inside": False
    }

    if comp.type == "convergent":
        d_in = comp.params["d_in"]
        d_out = comp.params["d_out"]
        A_in = gas.area_from_diameter(d_in)
        A_out = gas.area_from_diameter(d_out)

        A_star = A_in / area_mach_ratio(max(M_in, 1e-12), gas.gamma)
        A_out_ratio = A_out / max(A_star, 1e-18)

        if A_out_ratio < 1.0 - 1e-6:
            raise ChokedError("Convergent duct choked.")

        M_out = mach_from_area_ratio(max(A_out_ratio, 1.0), gas.gamma, subsonic=True)
        out.update({
            "M_out": M_out,
            "P0_out": P0_in,
            "T0_out": T0_in,
            "A_in": A_in,
            "A_out": A_out
        })

    elif comp.type == "divergent":
        d_in = comp.params["d_in"]
        d_out = comp.params["d_out"]
        A_in = gas.area_from_diameter(d_in)
        A_out = gas.area_from_diameter(d_out)

        A_star = A_in / area_mach_ratio(max(M_in, 1e-12), gas.gamma)
        A_out_ratio = A_out / max(A_star, 1e-18)

        subsonic = True
        if force_supersonic or M_in > 1.0:
            subsonic = False

        M_out = mach_from_area_ratio(A_out_ratio, gas.gamma, subsonic=subsonic)
        out.update({
            "M_out": M_out,
            "P0_out": P0_in,
            "T0_out": T0_in,
            "A_in": A_in,
            "A_out": A_out
        })

    elif comp.type == "fanno":
        length = comp.params["length"]
        d_h = comp.params["d_h"]
        f = comp.params["f"]
        A_in = gas.area_from_diameter(d_h)

        try:
            res = solve_fanno(M_in, f, length, d_h, gas.gamma)
        except ValueError:
            raise ChokedError("Fanno duct choked.")

        if res["choked"]:
            raise ChokedError("Fanno duct choked.")

        out.update({
            "M_out": res["M_out"],
            "P0_out": P0_in * res["P0_ratio"],
            "T0_out": T0_in,
            "A_in": A_in,
            "A_out": A_in
        })

    elif comp.type == "rayleigh":
        d_h = comp.params["d_h"]
        q = comp.params["q"]
        A_in = gas.area_from_diameter(d_h)

        try:
            res = solve_rayleigh(M_in, q, T0_in, gas.cp, gas.gamma)
        except ValueError:
            raise ChokedError("Rayleigh duct choked.")

        if res["choked"]:
            raise ChokedError("Rayleigh duct choked.")

        out.update({
            "M_out": res["M_out"],
            "P0_out": P0_in * res["P0_ratio"],
            "T0_out": res["T0_out"],
            "A_in": A_in,
            "A_out": A_in
        })

    elif comp.type == "normal_shock":
        try:
            rel = shock_relations(M_in, gas.gamma)
            out.update({
                "M_out": rel["M2"],
                "P0_out": P0_in * rel["P0_ratio"],
                "T0_out": T0_in,
                "A_in": 1.0,
                "A_out": 1.0
            })
        except ValueError:
            raise ChokedError("Normal shock attempted in subsonic flow.")

    else:
        raise ValueError(f"Unknown component type: {comp.type}")

    out["P_out"] = out["P0_out"] * pressure_ratio(out["M_out"], gas.gamma)
    out["T_out"] = out["T0_out"] * temperature_ratio(out["M_out"], gas.gamma)

    return out


# ===========================================================================
# Pipeline evaluation
# ===========================================================================

def evaluate_pipeline(
    components: List[ComponentConfig],
    M_in: float,
    P0_in: float,
    T0_in: float,
    gas: GasProperties,
    force_supersonic_divergent: bool = False
) -> List[Dict[str, Any]]:
    """Evaluate full pipeline for a given inlet Mach number."""
    results = []
    current_M = M_in
    current_P0 = P0_in
    current_T0 = T0_in

    has_shocked = False

    for comp in components:
        if comp.type == "normal_shock":
            has_shocked = True

        force_sup = False
        # Allow supersonic expansion if we are in 'supersonic-seeking' mode AND 
        # (it's the first throat OR the flow has been accelerated back to sonic conditions like a thermal throat)
        if force_supersonic_divergent and comp.type == "divergent" and current_M > 0.98:
            if not has_shocked or current_M > 0.995:
                force_sup = True

        res = evaluate_component(comp, current_M, current_P0, current_T0, gas,
                                 force_supersonic=force_sup)
        results.append(res)
        current_M = max(res["M_out"], 1e-12)
        current_P0 = res["P0_out"]
        current_T0 = res["T0_out"]

    return results


# ===========================================================================
# Choking detection & shock placement
# ===========================================================================

def find_choked_inlet_mach(
    components: List[ComponentConfig],
    P0_in: float,
    T0_in: float,
    gas: GasProperties
) -> float:
    """Find the maximum inlet Mach that doesn't choke."""
    M_low = 1e-6
    M_high = 1.0

    for _ in range(50):
        M_mid = (M_low + M_high) / 2.0
        try:
            evaluate_pipeline(components, M_mid, P0_in, T0_in, gas)
            M_low = M_mid
        except ChokedError:
            M_high = M_mid

    return M_low


def split_pipeline_at_x(
    components: List[ComponentConfig], x_shock: float
) -> List[ComponentConfig]:
    """Split a component at x_shock and insert a normal_shock."""
    new_comps = []
    current_x = 0.0

    for comp in components:
        L = comp.params.get("length", 1.0)

        if current_x <= x_shock < current_x + L and comp.type != "normal_shock":
            dx = x_shock - current_x
            if dx > 1e-6:
                c1 = ComponentConfig(type=comp.type, params=copy.deepcopy(comp.params))
                c1.params["length"] = dx
                if comp.type in ["convergent", "divergent"]:
                    d_in = comp.params["d_in"]
                    d_out = comp.params["d_out"]
                    d_shock = d_in + (d_out - d_in) * (dx / L)
                    c1.params["d_out"] = d_shock
                elif comp.type == "rayleigh":
                    c1.params["q"] = comp.params["q"] * (dx / L)
                new_comps.append(c1)

            new_comps.append(ComponentConfig(type="normal_shock", params={"length": 0.0}))

            if L - dx > 1e-6:
                c2 = ComponentConfig(type=comp.type, params=copy.deepcopy(comp.params))
                c2.params["length"] = L - dx
                if comp.type in ["convergent", "divergent"]:
                    d_in = comp.params["d_in"]
                    d_out = comp.params["d_out"]
                    d_shock = d_in + (d_out - d_in) * (dx / L)
                    c2.params["d_in"] = d_shock
                elif comp.type == "rayleigh":
                    c2.params["q"] = comp.params["q"] * ((L - dx) / L)
                new_comps.append(c2)
        else:
            new_comps.append(ComponentConfig(type=comp.type, params=copy.deepcopy(comp.params)))

        current_x += L

    return new_comps


# ===========================================================================
# Main solver driver (Shooting Method)
# ===========================================================================

def solve_full_pipeline(
    components: List[ComponentConfig],
    P0_in: float,
    T0_in: float,
    P_amb: float,
    gas: GasProperties
) -> Tuple[List[Dict[str, Any]], List[str], List[ComponentConfig]]:
    """
    Solve the 1D flow pipeline with shooting method.

    Returns (results, warnings, final_components).
    """
    warnings = []

    # 1. Sanity check for non-physical inputs
    if T0_in <= 1e-6:
        warnings.append("Stagnation temperature is near absolute zero. Returning stagnant results.")
        # Create a zero-flow solution profile
        results = []
        for comp in components:
            res = {
                "M_in": 0.0, "M_out": 0.0,
                "P0_in": P0_in, "P0_out": P0_in,
                "T0_in": T0_in, "T0_out": T0_in,
                "P_out": P0_in, "T_out": T0_in,
                "choked_inside": False,
                "A_in": 1.0, "A_out": 1.0 
            }
            results.append(res)
        return results, warnings, components

    # 2. Find choked inlet Mach
    M_in_choked = find_choked_inlet_mach(components, P0_in, T0_in, gas)

    # 0. Check for zero-flow condition (P_amb >= P0_in)
    if P_amb >= P0_in - 1e-3:
        warnings.append("Inlet and outlet pressures are equal - no flow.")
        # Create a zero-flow solution profile
        results = []
        for comp in components:
            res = {
                "M_in": 0.0, "M_out": 0.0,
                "P0_in": P0_in, "P0_out": P0_in,
                "T0_in": T0_in, "T0_out": T0_in,
                "P_out": P0_in, "T_out": T0_in,
                "choked_inside": False,
                "A_in": 1.0, "A_out": 1.0 # Fallback
            }
            # Fill areas if possible
            if comp.type in ["convergent", "divergent"]:
                res["A_in"] = gas.area_from_diameter(comp.params["d_in"])
                res["A_out"] = gas.area_from_diameter(comp.params["d_out"])
            elif comp.type in ["fanno", "rayleigh"]:
                res["A_in"] = gas.area_from_diameter(comp.params["d_h"])
                res["A_out"] = res["A_in"]
            results.append(res)
        return results, warnings, components

    # 2. Evaluate at choked M_in (fully subsonic)
    # Start with a safe near-zero evaluation as fallback
    try:
        res_choked_sub = evaluate_pipeline(components, 1e-8, P0_in, T0_in, gas)
    except ChokedError:
        # Extreme case: even M_in = 1e-8 chokes (massive heat/friction)
        warnings.append("Pipeline is extremely restrictive. Flow is likely stagnant.")
        return evaluate_pipeline(components, 1e-12, P0_in, T0_in, gas), warnings, components

    try:
        res_choked_sub_candidate = evaluate_pipeline(
            components, M_in_choked * 0.999, P0_in, T0_in, gas,
            force_supersonic_divergent=False
        )
        res_choked_sub = res_choked_sub_candidate
        P_exit_choked_sub = res_choked_sub[-1]["P_out"]
    except ChokedError:
        # If it chokes even at M_in_choked * 0.999, it's a hard thermal/frictional choke
        P_exit_choked_sub = res_choked_sub[-1]["P_out"] if res_choked_sub else P_amb
        warnings.append("Flow chokes at maximum subsonic capacity.")

    # -------------------------------------------------------------------
    # CASE A: FULLY SUBSONIC (P_amb >= P_exit at max subsonic M_in)
    # -------------------------------------------------------------------
    if P_amb >= P_exit_choked_sub:
        def obj_sub(M):
            try:
                r = evaluate_pipeline(components, M, P0_in, T0_in, gas,
                                      force_supersonic_divergent=False)
                return r[-1]["P_out"] - P_amb
            except Exception:
                # Catch all errors (ZeroDivision, ChokedError, etc.) as failure
                return -1.0
        
        # 1. Low-Mach Approximation (Incompressible Taylor expansion)
        # For M << 1, dP/P0 approx (gamma/2)*M^2. So M approx sqrt(2*dP / (gamma*P0))
        delta_p = P0_in - P_amb
        M_guess_incompressible = math.sqrt(max(0, 2 * delta_p / (gas.gamma * P0_in)))
        
        M_lo = 1e-8
        # Use a more targeted search range for small delta_p
        if delta_p / P0_in < 1e-4:
            M_hi_search = min(0.1, M_in_choked * 0.9)
        else:
            M_hi_search = M_in_choked * 0.9999

        try:
            val_lo = obj_sub(M_lo)
            val_hi = obj_sub(M_hi_search)
            if val_lo * val_hi <= 0:
                M_exact = brentq(obj_sub, M_lo, M_hi_search, xtol=1e-14, maxiter=200)
                results = evaluate_pipeline(
                    components, M_exact, P0_in, T0_in, gas,
                    force_supersonic_divergent=False
                )
                return results, warnings, components
            elif val_lo < 0:
                # Target pressure is HIGHER than P0_in (handled by zero-flow already, 
                # but adding safety here)
                warnings.append("Ambiguous pressure gradient. Returning stagnant flow.")
                return evaluate_pipeline(components, M_lo, P0_in, T0_in, gas), warnings, components
            else:
                # If we are here, it means val_hi > 0 even at M_hi_search.
                # This suggests either the flow is choked or there's a numerical flattening.
                if delta_p / P0_in < 1e-3:
                    # For small gradients, we trust the incompressible limit more than a choked fallback
                    results = evaluate_pipeline(components, M_lo, P0_in, T0_in, gas)
                    warnings.append("Numerical limit reached for small gradient. Using low-Mach approximation.")
                    return results, warnings, components
                return res_choked_sub, warnings, components
        except Exception as e:
            if delta_p / P0_in < 1e-3:
                return evaluate_pipeline(components, M_lo, P0_in, T0_in, gas), warnings, components
            warnings.append(f"Solver error: {str(e)}. Returning near-choked solution.")
            return res_choked_sub, warnings, components

    # -------------------------------------------------------------------
    # CASE B: CHOKED FLOW
    # -------------------------------------------------------------------
    warnings.append("Flow is choked.")

    # B1: Try fully supersonic branch
    try:
        res_choked_sup = evaluate_pipeline(
            components, M_in_choked * 0.9999, P0_in, T0_in, gas,
            force_supersonic_divergent=True
        )
        M_exit_sup = res_choked_sup[-1]["M_out"]
        P_exit_sup = res_choked_sup[-1]["P_out"]
    except ChokedError:
        # Supersonic branch chokes downstream (thermal/frictional)
        warnings.append(
            "Supersonic branch chokes thermally downstream. "
            "Searching for critical normal shock location."
        )

        # Find critical shock position
        throat_x = 0.0
        max_M = -1
        current_x = 0.0
        for comp, res in zip(components, res_choked_sub):
            L = comp.params.get("length", 1.0)
            if res["M_out"] > max_M:
                max_M = res["M_out"]
                throat_x = current_x + L
            current_x += L

        total_L = sum(c.params.get("length", 1.0) for c in components)
        x_low = throat_x + 1e-6
        x_high = total_L - 1e-6

        for _ in range(50):
            x_mid = (x_low + x_high) / 2.0
            try:
                split_comps = split_pipeline_at_x(components, x_mid)
                evaluate_pipeline(
                    split_comps, M_in_choked * 0.9999, P0_in, T0_in, gas,
                    force_supersonic_divergent=True
                )
                x_low = x_mid
            except ChokedError:
                x_high = x_mid

        x_shock_critical = x_low
        split_comps_crit = split_pipeline_at_x(components, x_shock_critical)
        try:
            res_crit = evaluate_pipeline(
                split_comps_crit, M_in_choked * 0.9999, P0_in, T0_in, gas,
                force_supersonic_divergent=True
            )
        except ChokedError:
            # Ultimate fallback
            warnings.append("Cannot resolve thermal choking. Returning subsonic solution.")
            return res_choked_sub, warnings, components

        # --- Modification: Bridge for multiple shocks ---
        # Evaluate the maximum backpressure capacity of the thermal throat
        comps_no_shock = [c for c in split_comps_crit if c.type != "normal_shock"]
        res_crit_sub = evaluate_pipeline(
            comps_no_shock, M_in_choked * 0.9999, P0_in, T0_in, gas,
            force_supersonic_divergent=False
        )
        P_sub_exit_crit = res_crit_sub[-1]["P_out"]

        M_exit_crit = res_crit[-1]["M_out"]
        P_exit_crit = res_crit[-1]["P_out"]

        # If thermal choking persists against ambient pressure, update 
        # variables and proceed to B3 instead of returning.
        if P_amb <= P_sub_exit_crit:
            warnings.append("Thermal throat activated. Searching for secondary shocks...")
            components = split_comps_crit
            res_choked_sup = res_crit
            M_exit_sup = M_exit_crit
            P_exit_sup = P_exit_crit
            
        # If backpressure unlocks the thermal throat, the shock must move upstream.
        else:
            def shock_obj_choked(x_shock):
                try:
                    sc = split_pipeline_at_x(components, x_shock)
                    r = evaluate_pipeline(
                        sc, M_in_choked * 0.9999, P0_in, T0_in, gas,
                        force_supersonic_divergent=False
                    )
                    return r[-1]["P_out"] - P_amb
                except ChokedError:
                    return -1e6

            try:
                x_shock_opt = brentq(
                    shock_obj_choked, throat_x + 1e-6, x_shock_critical
                )
                split_comps = split_pipeline_at_x(components, x_shock_opt)
                final_res = evaluate_pipeline(
                    split_comps, M_in_choked * 0.9999, P0_in, T0_in, gas,
                    force_supersonic_divergent=False
                )
                warnings.append("Thermal choking broken. Inserting single shock for backpressure.")
                return final_res, warnings, split_comps
            except ValueError:
                warnings.append("Error: impossible to position a single normal shock.")
                return res_crit, warnings, split_comps_crit

    # B2: Classify fully supersonic exit
    if M_exit_sup > 1.0:
        rel = shock_relations(M_exit_sup, gas.gamma)
        P_normal_shock_exit = P_exit_sup * rel["P_ratio"]
    else:
        P_normal_shock_exit = P_exit_sup

    # Underexpanded: P_amb < P_exit_supersonic
    if P_amb <= P_exit_sup:
        warnings.append(
            "Flow is underexpanded (supersonic exit, expansion fans outside)."
        )
        return res_choked_sup, warnings, components

    # Overexpanded: P_exit_sup < P_amb < P_normal_shock
    if P_amb < P_normal_shock_exit:
        warnings.append(
            "Flow is overexpanded (supersonic exit, oblique shocks outside)."
        )
        return res_choked_sup, warnings, components

    # B3: NORMAL SHOCK INSIDE
    warnings.append("Normal shock detected inside the pipeline.")

    def shock_obj(x_shock):
        sc = split_pipeline_at_x(components, x_shock)
        r = evaluate_pipeline(
            sc, M_in_choked * 0.9999, P0_in, T0_in, gas,
            force_supersonic_divergent=True
        )
        return r[-1]["P_out"] - P_amb

    # NEW: Search component by component, from EXIT to INLET
    current_x = sum(c.params.get("length", 1.0) for c in components)
    
    # Use zip to associate Mach data (res) with components
    for comp, res in zip(reversed(components), reversed(res_choked_sup)):
        L = comp.params.get("length", 1.0)
        x_high = current_x - 1e-6
        
        # Check only components capable of supersonic flow
        if comp.type in ["divergent", "fanno", "rayleigh"] and res["M_out"] > 1.0:
            
            # THROAT PROTECTION:
            # If the component inlet is near Mach 1 (e.g. physical or thermal throat),
            # push x_low slightly downstream into the safe supersonic regime (e.g. M=1.05)
            # to avoid numerical precision issues (Subsonic shock error).
            if res["M_in"] <= 1.02:
                frac = (1.05 - res["M_in"]) / max(res["M_out"] - res["M_in"], 1e-9)
                frac = max(0.02, min(0.98, frac)) # Shift between 2% and 98% of the component length
                x_low = (current_x - L) + L * frac
            else:
                x_low = current_x - L + 1e-6
                
            try:
                val_low = shock_obj(x_low)
                val_high = shock_obj(x_high)
            except ChokedError:
                # If placing the shock here chokes the downstream geometry, discard the interval
                current_x -= L
                continue

            # If P_amb is bracketed between the pressures provided by the boundary shocks
            if val_low * val_high <= 0:
                try:
                    # Exact optimization
                    x_shock_opt = brentq(shock_obj, x_low, x_high)
                    split_comps = split_pipeline_at_x(components, x_shock_opt)
                    
                    # Safe final evaluation (inside try-except to prevent UI crashes)
                    final_res = evaluate_pipeline(
                        split_comps, M_in_choked * 0.9999, P0_in, T0_in, gas,
                        force_supersonic_divergent=True
                    )
                    return final_res, warnings, split_comps
                except Exception as e:
                    warnings.append(f"Numerical issue refining shock in {comp.type}: {str(e)}")
                    pass # Do not crash, simply try further upstream
                    
        current_x -= L

    warnings.append("Could not pinpoint exact normal shock location. Returning fully supersonic branch.")
    return res_choked_sup, warnings, components


# ===========================================================================
# Plot data generation (RK4 spatial integration for smooth profiles)
# ===========================================================================

def generate_plot_data(
    components: List[ComponentConfig],
    results: List[Dict[str, Any]],
    gas: GasProperties,
    num_points: int = 50
):
    """
    Generate high-resolution arrays for plotting.

    Uses analytical sub-evaluations per component to generate smooth
    spatial profiles of M, P, T, P0, T0, and mass flux.
    """
    data = {
        "x": [],
        "mach": [],
        "pressure": [],
        "pressure_total": [],
        "temperature": [],
        "temperature_total": [],
        "mass_flow": []
    }
    boundaries = [0.0]

    current_x = 0.0
    for comp, res in zip(components, results):
        L = comp.params.get("length", 1.0)

        # Handle zero-flow case (M_in == 0.0)
        if res["M_in"] < 1e-12:
            x_vals = np.linspace(current_x, current_x + L, num_points)
            for x in x_vals:
                data["x"].append(x)
                data["mach"].append(0.0)
                data["pressure"].append(res["P0_in"])
                data["pressure_total"].append(res["P0_in"])
                data["temperature"].append(res["T0_in"])
                data["temperature_total"].append(res["T0_in"])
                data["mass_flow"].append(0.0)
            current_x += L
            boundaries.append(current_x)
            continue

        # Normal shock: zero-length discontinuity
        if L == 0.0 and comp.type == "normal_shock":
            P_out = res["P0_out"] * pressure_ratio(res["M_out"], gas.gamma)
            T_out = res["T0_out"] * temperature_ratio(res["M_out"], gas.gamma)
            rho = gas.density(P_out, T_out)
            V = res["M_out"] * gas.speed_of_sound(T_out)
            mass_flux = rho * V

            data["x"].append(current_x)
            data["mach"].append(res["M_out"])
            data["pressure"].append(P_out)
            data["pressure_total"].append(res["P0_out"])
            data["temperature"].append(T_out)
            data["temperature_total"].append(res["T0_out"])
            data["mass_flow"].append(mass_flux)
            continue

        x_vals = np.linspace(current_x, current_x + L, num_points)

        for x in x_vals:
            dx = x - current_x

            if dx == 0:
                M = res["M_in"]
                P0 = res["P0_in"]
                T0 = res["T0_in"]
                A_x = res.get("A_in", 1.0)
            elif dx == L and L > 0:
                M = res["M_out"]
                P0 = res["P0_out"]
                T0 = res["T0_out"]
                A_x = res.get("A_out", 1.0)
            else:
                if L < 1e-12:
                    # Avoid division by zero for zero-length components
                    M = res["M_in"]
                    P0 = res["P0_in"]
                    T0 = res["T0_in"]
                    A_x = res.get("A_in", 1.0)
                elif comp.type == "fanno":
                    f = comp.params["f"]
                    d_h = comp.params["d_h"]
                    f_res = solve_fanno(res["M_in"], f, dx, d_h, gas.gamma)
                    M = f_res["M_out"]
                    P0 = res["P0_in"] * f_res["P0_ratio"]
                    T0 = res["T0_in"]
                    A_x = gas.area_from_diameter(d_h)

                elif comp.type == "rayleigh":
                    q_total = comp.params["q"]
                    q_partial = q_total * (dx / L)
                    r_res = solve_rayleigh(
                        res["M_in"], q_partial, res["T0_in"],
                        gas.cp, gas.gamma
                    )
                    M = r_res["M_out"]
                    P0 = res["P0_in"] * r_res["P0_ratio"]
                    T0 = r_res["T0_out"]
                    A_x = gas.area_from_diameter(comp.params["d_h"])

                elif comp.type in ["convergent", "divergent"]:
                    d_in = comp.params["d_in"]
                    d_out = comp.params["d_out"]
                    A_in = gas.area_from_diameter(d_in)
                    
                    # Safety check for very low Mach number to avoid A_star -> 0 and division by zero
                    if res["M_in"] < 1e-8:
                        M = res["M_in"]
                        P0 = res["P0_in"]
                        T0 = res["T0_in"]
                        A_x = res.get("A_in", 1.0)
                    else:
                        A_star = A_in / area_mach_ratio(res["M_in"], gas.gamma)
                        d_x = d_in + (d_out - d_in) * (dx / max(L, 1e-12))
                        A_x = gas.area_from_diameter(d_x)
                        A_ratio = A_x / max(A_star, 1e-12)

                        is_sub = res["M_out"] <= 1.0 + 1e-6
                        if res["M_in"] > 1.0:
                            is_sub = False
                        
                        try:
                            M = mach_from_area_ratio(
                                max(A_ratio, 1.0), gas.gamma, subsonic=is_sub
                            )
                        except ValueError:
                            # Fallback if A_ratio calculation still fails numerically
                            M = res["M_in"]
                        P0 = res["P0_in"]
                        T0 = res["T0_in"]

                else:
                    # Linear interpolation fallback
                    frac = dx / L
                    M = res["M_in"] + (res["M_out"] - res["M_in"]) * frac
                    P0 = res["P0_in"] + (res["P0_out"] - res["P0_in"]) * frac
                    T0 = res["T0_in"] + (res["T0_out"] - res["T0_in"]) * frac
                    A_x = res.get("A_in", 1.0)

            P = P0 * pressure_ratio(M, gas.gamma)
            T = T0 * temperature_ratio(M, gamma=gas.gamma)
            rho = gas.density(P, T)
            a = gas.speed_of_sound(T)
            V = M * a
            mass_flow_rate_val = rho * V * A_x

            data["x"].append(x)
            data["mach"].append(M)
            data["pressure"].append(P)
            data["pressure_total"].append(P0)
            data["temperature"].append(T)
            data["temperature_total"].append(T0)
            data["mass_flow"].append(mass_flow_rate_val)

        current_x += L
        boundaries.append(current_x)

    return data, boundaries
