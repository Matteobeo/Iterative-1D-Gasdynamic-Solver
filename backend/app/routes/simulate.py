from fastapi import APIRouter, HTTPException
from app.models import SimulationRequest, SimulationResponse
from app.solver.gas import GasProperties
from app.solver.iterative_solver import solve_full_pipeline, generate_plot_data
import numpy as np

router = APIRouter()


def compute_summary(request: SimulationRequest, data: dict) -> dict:
    if not data or not data.get("mass_flow"):
        return {}
        
    gamma = request.gamma
    R = request.R
    P0 = request.P0
    P_amb = request.P_amb
    
    mdot = data["mass_flow"][-1]
    P_e = data["pressure"][-1]
    P0_e = data["pressure_total"][-1]
    T_e = data["temperature"][-1]
    M_e = data["mach"][-1]
    
    a_e = (gamma * R * max(0.0, T_e)) ** 0.5
    V_e = M_e * a_e
    
    A_e = 1.0
    gas = GasProperties(gamma=gamma, R=R)
    for comp in reversed(request.components):
        if comp.type in ["convergent", "divergent"]:
            A_e = gas.area_from_diameter(comp.params.get("d_out", 1.0))
            break
        elif comp.type in ["fanno", "rayleigh"]:
            A_e = gas.area_from_diameter(comp.params.get("d_h", 1.0))
            break
        elif comp.type == "solid_grain":
            continue  # Grain has no geometric area, skip
            
    thrust = mdot * V_e + (P_e - P_amb) * A_e

    # Cap P0_e: CFD numerical dissipation can cause a tiny overshoot above P0.
    # Physically impossible, so we enforce the conservation constraint.
    P0_e = min(P0_e, P0)
    
    # P* at exit: the static pressure if exit Mach were exactly 1.0
    P_crit_exit = P0_e * (2 / (gamma + 1)) ** (gamma / (gamma - 1))
    
    # The exact ambient pressure that still allows the nozzle to choke,
    # accounting for all friction and heat losses in the pipeline.
    # 1. Identifica la gola nel CFD per calcolare le perdite REALI fino al punto critico
    throat_x = 0.0
    d_min = 1e10
    curr_x = 0.0
    for c in request.components:
        if c.type == "convergent":
            if c.params["d_out"] < d_min:
                d_min = c.params["d_out"]
                throat_x = curr_x + c.params["length"]
        elif c.type == "divergent":
            if c.params["d_in"] < d_min:
                d_min = c.params["d_in"]
                throat_x = curr_x
        curr_x += c.params.get("length", 0.0)
    
    # Trova l'indice più vicino alla gola nei dati CFD
    t_idx = 0
    if data["x"]:
        t_idx = np.argmin(np.abs(np.array(data["x"]) - throat_x))
    P0_throat_cfd = data["pressure_total"][t_idx]
    
    # 2. Calcola il limite di Choking (portata) basandosi sulle perdite fino alla gola
    # Questo valore è fisso e non dipende dalla posizione dell'urto a valle.
    try:
        from app.solver.iterative_solver import find_choked_inlet_mach, evaluate_pipeline
        M_in_choked = find_choked_inlet_mach(request.components, P0, request.T0, gas)
        res_choked = evaluate_pipeline(
            request.components, M_in_choked, P0, request.T0, gas,
            force_supersonic_divergent=False
        )
        P_amb_choke_ideal = res_choked[-1]["P_out"]
    except Exception:
        P_amb_choke_ideal = P0 * (2 / (gamma + 1)) ** (gamma / (gamma - 1))

    if request.solver_type == "general":
        choking_key = "CFD Choking Threshold"
        # Usiamo P0 alla gola come riferimento per le perdite subsoniche
        correction_factor = P0_throat_cfd / P0 if P0 > 0 else 1.0
        P_amb_choke = P_amb_choke_ideal * correction_factor
    else:
        choking_key = "Choking Threshold"
        P_amb_choke = P_amb_choke_ideal

    result = {
        "Thrust": {"value": thrust, "unit": "N"},
        "Exit Velocity": {"value": V_e, "unit": "m/s"},
        "Exit Static P.": {"value": P_e, "unit": "Pa"},
        "Critical Exit P.": {"value": P_crit_exit, "unit": "Pa"},
        choking_key: {"value": P_amb_choke, "unit": "Pa"},
        "Mass Flow": {"value": mdot, "unit": "kg/s"}
    }

    # =============================================================
    # Exit Shock P_amb: P_amb che posiziona l'urto esattamente all'uscita.
    # =============================================================
    try:
        from scipy.optimize import brentq

        def _isentropic_mach_from_area_ratio(AR, gam):
            def eq(M):
                gm1 = gam - 1.0
                return (1.0/M) * ((2.0/(gam+1.0)) * (1.0 + gm1/2.0 * M**2)) ** ((gam+1.0)/(2.0*gm1)) - AR
            try:
                return brentq(eq, 1.001, 20.0, xtol=1e-8)
            except ValueError:
                return None

        def _rankine_hugoniot_p_amb(M_sup, P0_ref, gam):
            isentropic_p = P0_ref * (1.0 + (gam-1.0)/2.0 * M_sup**2) ** (-gam/(gam-1.0))
            p2_ratio = 1.0 + (2.0 * gam / (gam + 1.0)) * (M_sup**2 - 1.0)
            return isentropic_p * p2_ratio

        # Determina l'ultimo componente divergente
        div_comp = None
        for c in reversed(request.components):
            if c.type == "divergent":
                div_comp = c
                break
        
        shock_p_amb = None
        if div_comp:
            d_throat = d_min
            d_exit = div_comp.params.get("d_out")
            if d_throat and d_exit and d_exit > d_throat:
                AR = (d_exit / d_throat) ** 2
                M_exit_sup = _isentropic_mach_from_area_ratio(AR, gamma)
                if M_exit_sup:
                    # Usiamo P0 alla gola (che include perdite subsoniche) 
                    # come riferimento per la gola isentropica equivalente
                    shock_p_amb = _rankine_hugoniot_p_amb(M_exit_sup, P0_throat_cfd, gamma)

        if shock_p_amb is not None and shock_p_amb > 0:
            result["Shock Exit P_amb"] = {"value": shock_p_amb, "unit": "Pa"}

    except Exception:
        pass

    return result




@router.post("/simulate", response_model=SimulationResponse)
async def simulate(request: SimulationRequest):
    """
    Receive duct configuration and boundary conditions,
    run the gas dynamics solver, and return results.
    """
    try:
        if request.is_real:
            from app.solver.gas import RealGasProperties
            gas = RealGasProperties(gamma=request.gamma, R=request.R, a=request.a, b=request.b)
        else:
            gas = GasProperties(gamma=request.gamma, R=request.R)
        
        if not request.components:
            raise ValueError("No components provided.")
            
        import json
        with open("last_request.json", "w") as f:
            f.write(request.json())
            
            
        if request.solver_type == "general":
            from app.solver.hybrid_solver import solve_full_pipeline as solve_hybrid, generate_plot_data as plot_hybrid
            import hashlib, json
            
            # Generate a unique hash based on request data to avoid stale caching
            req_data = {
                "P0": request.P0, "T0": request.T0, "P_amb": request.P_amb,
                "comps": [{"type": c.type, "params": c.params} for c in request.components]
            }
            request_hash = hashlib.md5(json.dumps(req_data, sort_keys=True).encode()).hexdigest()
            
            results, warnings, final_comps = solve_hybrid(
                components=request.components,
                P0_in=request.P0,
                T0_in=request.T0,
                P_amb=request.P_amb,
                gas=gas,
                request_hash=request_hash
            )
            
            data, boundaries, labels = plot_hybrid(final_comps, results, gas, request_hash=request_hash)
            summary = compute_summary(request, data)
            
            return SimulationResponse(
                success=True,
                warnings=["Advanced General Solver (BETA) used."] + warnings,
                data=data,
                component_boundaries=boundaries,
                component_labels=labels,
                summary=summary
            )

        results, warnings, split_comps = solve_full_pipeline(
            components=request.components,
            P0_in=request.P0,
            T0_in=request.T0,
            P_amb=request.P_amb,
            gas=gas
        )
        
        data, boundaries, labels = generate_plot_data(split_comps, results, gas)
        summary = compute_summary(request, data)
        
        return SimulationResponse(
            success=True,
            warnings=warnings,
            data=data,
            component_boundaries=boundaries,
            component_labels=labels,
            summary=summary
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return SimulationResponse(
            success=False,
            error=str(e),
            warnings=["Simulation failed."]
        )
