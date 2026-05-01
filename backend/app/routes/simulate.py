from fastapi import APIRouter, HTTPException
from app.models import SimulationRequest, SimulationResponse
from app.solver.gas import GasProperties
from app.solver.iterative_solver import solve_full_pipeline, generate_plot_data

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
    try:
        from app.solver.iterative_solver import find_choked_inlet_mach, evaluate_pipeline
        M_in_choked = find_choked_inlet_mach(request.components, P0, request.T0, gas)
        res_choked = evaluate_pipeline(
            request.components, M_in_choked, P0, request.T0, gas,
            force_supersonic_divergent=False
        )
        P_amb_choke_ideal = res_choked[-1]["P_out"]
        P0_exit_ideal = res_choked[-1]["P0_out"]
    except Exception:
        P_amb_choke_ideal = P0 * (2 / (gamma + 1)) ** (gamma / (gamma - 1))
        P0_exit_ideal = P0
    
    if request.solver_type == "general":
        choking_key = "CFD Est. Choking P_amb"
        correction_factor = P0_e / P0_exit_ideal if P0_exit_ideal > 0 else 1.0
        P_amb_choke = P_amb_choke_ideal * correction_factor
    else:
        choking_key = "Choking P_amb"
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
    # Exit Shock P_amb: P_amb that places a normal shock at the exit.
    #
    # Three physical cases:
    #   A) Last component = Divergent  → isentropic area-ratio Mach (geometrico, preciso)
    #   B) Last component = Fanno      → area costante, urto all'uscita, usa M_e CFD
    #   C) Last component = Rayleigh   → il choking termico sposta l'urto nel componente
    #                                    precedente (tipicamente un divergente): cercare lì
    # =============================================================
    try:
        from scipy.optimize import brentq

        def _isentropic_mach_from_area_ratio(AR, gam):
            """Inverte A/A* per il ramo supersonico M > 1."""
            def eq(M):
                gm1 = gam - 1.0
                return (1.0/M) * ((2.0/(gam+1.0)) * (1.0 + gm1/2.0 * M**2)) ** ((gam+1.0)/(2.0*gm1)) - AR
            try:
                return brentq(eq, 1.001, 20.0, xtol=1e-8)
            except ValueError:
                return None

        def _rankine_hugoniot_p_amb(M_sup, P0_ref, gam):
            """Applica R-H a M_sup e restituisce P_amb per urto all'uscita."""
            isentropic_p = P0_ref * (1.0 + (gam-1.0)/2.0 * M_sup**2) ** (-gam/(gam-1.0))
            p2_ratio = 1.0 + (2.0 * gam / (gam + 1.0)) * (M_sup**2 - 1.0)
            return isentropic_p * p2_ratio

        def _find_throat_diameter(comps):
            """Trova il diametro minimo di gola nella pipeline."""
            d_t = None
            for c in comps:
                if c.type == "convergent":
                    d = c.params.get("d_out")
                    if d and (d_t is None or d < d_t): d_t = d
                elif c.type == "divergent":
                    d = c.params.get("d_in")
                    if d and (d_t is None or d < d_t): d_t = d
            return d_t

        def _exit_shock_from_divergent(div_comp, comps, gam, P0_ref):
            """Calcola Exit Shock P_amb per un componente divergente."""
            d_throat = _find_throat_diameter(comps)
            d_exit   = div_comp.params.get("d_out")
            if not d_throat or not d_exit or d_exit <= d_throat:
                return None
            AR = (d_exit / d_throat) ** 2
            M_design = _isentropic_mach_from_area_ratio(AR, gam)
            if M_design and M_design > 1.0:
                return _rankine_hugoniot_p_amb(M_design, P0_ref, gam)
            return None

        # Determina l'ultimo componente significativo
        comps = request.components
        last_type = None
        last_comp = None
        for c in reversed(comps):
            if c.type not in ["normal_shock", "solid_grain"]:
                last_type = c.type
                last_comp = c
                break

        shock_p_amb = None

        # --- CASO A: uscita su Divergente ---
        if last_type == "divergent":
            shock_p_amb = _exit_shock_from_divergent(last_comp, comps, gamma, P0_e)

        # --- CASO B: uscita su Fanno (area costante, urto all'uscita Fanno) ---
        elif last_type == "fanno":
            if M_e > 1.0:
                shock_p_amb = _rankine_hugoniot_p_amb(M_e, P0_e, gamma)

        # --- CASO C: uscita su Rayleigh → urto nel componente precedente ---
        elif last_type == "rayleigh":
            # Cerca il componente immediatamente prima di Rayleigh
            prev_comp = None
            found_rayleigh = False
            for c in reversed(comps):
                if c.type == "rayleigh" and not found_rayleigh:
                    found_rayleigh = True
                    continue
                if found_rayleigh and c.type not in ["normal_shock", "solid_grain", "rayleigh"]:
                    prev_comp = c
                    break
            if prev_comp is not None and prev_comp.type == "divergent":
                shock_p_amb = _exit_shock_from_divergent(prev_comp, comps, gamma, P0_e)
            elif M_e > 1.0:
                # Fallback: Rayleigh con uscita ancora supersonica → R-H sul M_e
                shock_p_amb = _rankine_hugoniot_p_amb(M_e, P0_e, gamma)

        # --- CASO generico: qualsiasi altro tipo con M > 1 ---
        elif M_e > 1.0 and last_comp is not None:
            shock_p_amb = _rankine_hugoniot_p_amb(M_e, P0_e, gamma)

        if shock_p_amb is not None and shock_p_amb > 0:
            result["Exit Shock P_amb"] = {"value": shock_p_amb, "unit": "Pa"}

    except Exception:
        pass  # Non-critical: omit if anything fails

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
            
        if request.solver_type == "general":
            from app.solver.hybrid_solver import solve_full_pipeline as solve_hybrid, generate_plot_data as plot_hybrid
            
            results, warnings, final_comps = solve_hybrid(
                components=request.components,
                P0_in=request.P0,
                T0_in=request.T0,
                P_amb=request.P_amb,
                gas=gas
            )
            
            data, boundaries = plot_hybrid(final_comps, results, gas)
            summary = compute_summary(request, data)
            
            return SimulationResponse(
                success=True,
                warnings=["Advanced General Solver (BETA) used."] + warnings,
                data=data,
                component_boundaries=boundaries,
                summary=summary
            )

        results, warnings, split_comps = solve_full_pipeline(
            components=request.components,
            P0_in=request.P0,
            T0_in=request.T0,
            P_amb=request.P_amb,
            gas=gas
        )
        
        data, boundaries = generate_plot_data(split_comps, results, gas)
        summary = compute_summary(request, data)
        
        return SimulationResponse(
            success=True,
            warnings=warnings,
            data=data,
            component_boundaries=boundaries,
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
