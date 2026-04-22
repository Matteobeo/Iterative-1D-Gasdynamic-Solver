import numpy as np
from typing import List, Dict, Tuple, Any
from scipy.optimize import brentq
import copy

from app.models import ComponentConfig
from app.solver.gas import GasProperties
from app.solver.isentropic import (
    area_mach_ratio, mach_from_area_ratio,
    pressure_ratio, temperature_ratio
)
from app.solver.fanno import solve_fanno
from app.solver.rayleigh import solve_rayleigh
from app.solver.normal_shock import shock_relations


class ChokedError(Exception):
    pass


def evaluate_component(
    comp: ComponentConfig,
    M_in: float,
    P0_in: float,
    T0_in: float,
    gas: GasProperties,
    force_supersonic: bool = False
) -> Dict[str, Any]:
    """Evaluate a single component, marching from inlet to outlet."""
    
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
        
        # A_star doesn't change
        A_star = A_in / area_mach_ratio(M_in, gas.gamma)
        A_out_ratio = A_out / A_star
        
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
        
        A_star = A_in / area_mach_ratio(M_in, gas.gamma)
        A_out_ratio = A_out / A_star
        
        # If forced supersonic and incoming is ~1.0, we go supersonic
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
        length = comp.params["length"]
        d_h = comp.params["d_h"] # assuming circular pipe
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
                "A_in": 1.0, # dummy value, won't be used for plotting Area
                "A_out": 1.0
            })
        except ValueError:
            raise ChokedError("Normal shock attempted in subsonic flow.")

    else:
        raise ValueError(f"Unknown component type: {comp.type}")

    out["P_out"] = out["P0_out"] * pressure_ratio(out["M_out"], gas.gamma)
    out["T_out"] = out["T0_out"] * temperature_ratio(out["M_out"], gas.gamma)
    
    return out


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
            
        # Check if we should force supersonic (only if prev M is high enough and it's divergent)
        force_sup = False
        if force_supersonic_divergent and not has_shocked and comp.type == "divergent" and current_M > 0.9:
            force_sup = True
            
        res = evaluate_component(comp, current_M, current_P0, current_T0, gas, force_supersonic=force_sup)
        results.append(res)
        current_M = res["M_out"]
        current_P0 = res["P0_out"]
        current_T0 = res["T0_out"]
        
    return results


def find_choked_inlet_mach(
    components: List[ComponentConfig],
    P0_in: float,
    T0_in: float,
    gas: GasProperties
) -> float:
    """Find the maximum possible M_in that chokes the pipeline somewhere."""
    # Bisection to find max M_in
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


def split_pipeline_at_x(components: List[ComponentConfig], x_shock: float) -> List[ComponentConfig]:
    """Splits a component at a global position x_shock and inserts a normal_shock component."""
    new_comps = []
    current_x = 0.0
    
    for comp in components:
        L = comp.params.get("length", 1.0)
        
        # If the shock is within this component (and it's not already a shock)
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


def solve_full_pipeline(
    components: List[ComponentConfig],
    P0_in: float,
    T0_in: float,
    P_amb: float,
    gas: GasProperties
) -> Tuple[List[Dict[str, Any]], List[str], List[ComponentConfig]]:
    warnings = []
    
    # 1. Find choked M_in
    M_in_choked = find_choked_inlet_mach(components, P0_in, T0_in, gas)
    
    # 2. Evaluate at choked M_in (fully subsonic, M<1 everywhere)
    try:
        res_choked_sub = evaluate_pipeline(components, M_in_choked * 0.9999, P0_in, T0_in, gas, force_supersonic_divergent=False)
        P_exit_choked_sub = res_choked_sub[-1]["P_out"]
    except ChokedError:
        P_exit_choked_sub = P_amb  # Fallback if bisection boundary was too tight

    # ---------------------------------------------------------------
    # Case: FULLY SUBSONIC — back pressure is above the unchocking
    # threshold, so the throat never reaches M=1.
    # We MUST handle this entirely here and never fall through to
    # the supersonic/choked branch below.
    # ---------------------------------------------------------------
    if P_amb >= P_exit_choked_sub:
        def obj_sub(M):
            try:
                r = evaluate_pipeline(components, M, P0_in, T0_in, gas,
                                      force_supersonic_divergent=False)
                return r[-1]["P_out"] - P_amb
            except ChokedError:
                return -1.0  # Should not happen in subsonic regime

        M_lo = 1e-9
        M_hi = M_in_choked * 0.9999

        # Check that brentq has a proper bracket; at M→0, P_out ≈ P0 > P_amb
        try:
            val_lo = obj_sub(M_lo)
            val_hi = obj_sub(M_hi)

            if val_lo * val_hi <= 0:
                # Normal case: bracket is valid
                M_exact = brentq(obj_sub, M_lo, M_hi, xtol=1e-12, maxiter=200)
                results = evaluate_pipeline(components, M_exact, P0_in, T0_in, gas,
                                            force_supersonic_divergent=False)
                return results, warnings, components
            elif val_lo < 0:
                # P_amb > P0: gas barely moves; return near-stagnation state
                warnings.append("Back pressure equals or exceeds stagnation pressure. Flow is nearly stagnant.")
                results = evaluate_pipeline(components, M_lo, P0_in, T0_in, gas,
                                            force_supersonic_divergent=False)
                return results, warnings, components
            else:
                # Both positive: P_exit > P_amb even at M_in_choked, use choked state
                return res_choked_sub, warnings, components
        except Exception:
            # Last-resort fallback: return the nearly-choked subsonic result
            warnings.append("Could not find exact subsonic M_in; returning near-choked subsonic solution.")
            return res_choked_sub, warnings, components
            
    # Flow is choked
    warnings.append("Flow is choked.")
    
    # Evaluate supersonic branch
    try:
        res_choked_sup = evaluate_pipeline(components, M_in_choked * 0.9999, P0_in, T0_in, gas, force_supersonic_divergent=True)
        M_exit_sup = res_choked_sup[-1]["M_out"]
        P_exit_sup = res_choked_sup[-1]["P_out"]
    except ChokedError:
        warnings.append("Supersonic branch chokes thermally downstream. Searching for critical normal shock location.")
        
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
                evaluate_pipeline(split_comps, M_in_choked * 0.9999, P0_in, T0_in, gas, force_supersonic_divergent=True)
                x_low = x_mid
            except ChokedError:
                x_high = x_mid
                
        x_shock_critical = x_low
        split_comps_crit = split_pipeline_at_x(components, x_shock_critical)
        res_crit = evaluate_pipeline(split_comps_crit, M_in_choked * 0.9999, P0_in, T0_in, gas, force_supersonic_divergent=True)
        P_exit_crit = res_crit[-1]["P_out"]
        
        if P_amb <= P_exit_crit:
            warnings.append(f"Flow chokes thermally. Normal shock established at x={x_shock_critical:.4f} m to unchoke downstream.")
            return res_crit, warnings, split_comps_crit
            
        def shock_obj_choked(x_shock):
            try:
                split_comps = split_pipeline_at_x(components, x_shock)
                res = evaluate_pipeline(split_comps, M_in_choked * 0.9999, P0_in, T0_in, gas, force_supersonic_divergent=True)
                return res[-1]["P_out"] - P_amb
            except ChokedError:
                return -1e6
                
        try:
            x_shock_opt = brentq(shock_obj_choked, throat_x + 1e-6, x_shock_critical)
            split_comps = split_pipeline_at_x(components, x_shock_opt)
            final_res = evaluate_pipeline(split_comps, M_in_choked * 0.9999, P0_in, T0_in, gas, force_supersonic_divergent=True)
            warnings.append("Normal shock located in divergent section to match backpressure (thermal choking avoided).")
            return final_res, warnings, split_comps
        except ValueError:
            warnings.append("Failed to find exact shock location to match backpressure.")
            return res_crit, warnings, split_comps_crit
    
    if M_exit_sup > 1.0:
        rel = shock_relations(M_exit_sup, gas.gamma)
        P_normal_shock_exit = P_exit_sup * rel["P_ratio"]
    else:
        P_normal_shock_exit = P_exit_sup
    
    if P_amb <= P_exit_sup:
        warnings.append("Flow is underexpanded (supersonic exit, expansion fans outside).")
        return res_choked_sup, warnings, components
        
    if P_amb < P_normal_shock_exit:
        warnings.append("Flow is overexpanded (supersonic exit, oblique shocks outside).")
        return res_choked_sup, warnings, components
        
    # NORMAL SHOCK INSIDE THE PIPELINE
    warnings.append("Normal shock detected inside the pipeline.")
    
    total_L = sum(c.params.get("length", 1.0) for c in components)
    
    def shock_obj(x_shock):
        try:
            split_comps = split_pipeline_at_x(components, x_shock)
            res = evaluate_pipeline(split_comps, M_in_choked * 0.9999, P0_in, T0_in, gas, force_supersonic_divergent=True)
            return res[-1]["P_out"] - P_amb
        except ChokedError:
            # Shock placed too early causes secondary choking downstream
            return -1e6

    # Find the sonic throat location to bound the search
    throat_x = 0.0
    current_x = 0.0
    for comp, res in zip(components, res_choked_sup):
        L = comp.params.get("length", 1.0)
        if res["M_in"] <= 1.0 and res["M_out"] >= 1.0:
            throat_x = current_x + L * ((1.0 - res["M_in"]) / (res["M_out"] - res["M_in"] + 1e-9))
            break
        current_x += L
        
    x_low = throat_x + 1e-6
    x_high = total_L - 1e-6
    
    if x_low < x_high:
        val_low = shock_obj(x_low)
        val_high = shock_obj(x_high)
        
        if val_low * val_high <= 0:
            try:
                x_shock_opt = brentq(shock_obj, x_low, x_high)
                split_comps = split_pipeline_at_x(components, x_shock_opt)
                final_res = evaluate_pipeline(split_comps, M_in_choked * 0.9999, P0_in, T0_in, gas, force_supersonic_divergent=True)
                return final_res, warnings, split_comps
            except ValueError:
                pass
                
    warnings.append("Could not pinpoint exact normal shock location. Returning fully supersonic branch.")
    return res_choked_sup, warnings, components


def generate_plot_data(components: List[ComponentConfig], results: List[Dict[str, Any]], gas: GasProperties, num_points: int = 50):
    """Generate high-resolution arrays for plotting."""
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
        
        if L == 0.0 and comp.type == "normal_shock":
            # For a normal shock, we just append the downstream state at the exact same 'x'
            # to create a perfectly vertical line in the plots.
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
        
        for i, x in enumerate(x_vals):
            dx = x - current_x
            
            if dx == 0:
                M = res["M_in"]
                P0 = res["P0_in"]
                T0 = res["T0_in"]
            elif dx == L:
                M = res["M_out"]
                P0 = res["P0_out"]
                T0 = res["T0_out"]
            else:
                if comp.type == "fanno":
                    from app.solver.fanno import solve_fanno
                    f = comp.params["f"]
                    d_h = comp.params["d_h"]
                    f_res = solve_fanno(res["M_in"], f, dx, d_h, gas.gamma)
                    M = f_res["M_out"]
                    P0 = res["P0_in"] * f_res["P0_ratio"]
                    T0 = res["T0_in"]
                elif comp.type == "rayleigh":
                    from app.solver.rayleigh import solve_rayleigh
                    q_total = comp.params["q"]
                    q_partial = q_total * (dx / L)
                    r_res = solve_rayleigh(res["M_in"], q_partial, res["T0_in"], gas.cp, gas.gamma)
                    M = r_res["M_out"]
                    P0 = res["P0_in"] * r_res["P0_ratio"]
                    T0 = r_res["T0_out"]
                elif comp.type in ["convergent", "divergent"]:
                    d_in = comp.params["d_in"]
                    d_out = comp.params["d_out"]
                    A_in = gas.area_from_diameter(d_in)
                    from app.solver.isentropic import area_mach_ratio, mach_from_area_ratio
                    A_star = A_in / area_mach_ratio(res["M_in"], gas.gamma)
                    
                    d_x = d_in + (d_out - d_in) * (dx / L)
                    A_x = gas.area_from_diameter(d_x)
                    A_ratio = A_x / A_star
                    is_sub = res["M_out"] <= 1.0 + 1e-6
                    if res["M_in"] > 1.0:
                        is_sub = False
                    M = mach_from_area_ratio(max(A_ratio, 1.0), gas.gamma, subsonic=is_sub)
                    P0 = res["P0_in"]
                    T0 = res["T0_in"]
                else:
                    M = res["M_in"] + (res["M_out"] - res["M_in"]) * (dx / L)
                    P0 = res["P0_in"] + (res["P0_out"] - res["P0_in"]) * (dx / L)
                    T0 = res["T0_in"] + (res["T0_out"] - res["T0_in"]) * (dx / L)
                    
            P = P0 * pressure_ratio(M, gas.gamma)
            T = T0 * temperature_ratio(M, gas.gamma)
            rho = gas.density(P, T)
            a = gas.speed_of_sound(T)
            V = M * a
            mass_flux = rho * V
            
            data["x"].append(x)
            data["mach"].append(M)
            data["pressure"].append(P)
            data["pressure_total"].append(P0)
            data["temperature"].append(T)
            data["temperature_total"].append(T0)
            data["mass_flow"].append(mass_flux)
            
        current_x += L
        boundaries.append(current_x)
        
    return data, boundaries
