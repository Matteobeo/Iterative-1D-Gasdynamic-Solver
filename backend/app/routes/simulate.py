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
        P_amb_choke = res_choked[-1]["P_out"]
    except Exception:
        # Fallback to ideal isentropic calculation if something fails
        P_amb_choke = P0 * (2 / (gamma + 1)) ** (gamma / (gamma - 1))
    
    choking_key = "Ideal Choking P_amb" if request.solver_type == "general" else "Choking P_amb"

    return {
        "Thrust": {"value": thrust, "unit": "N"},
        "Exit Velocity": {"value": V_e, "unit": "m/s"},
        "Exit Static P.": {"value": P_e, "unit": "Pa"},
        "Critical Exit P.": {"value": P_crit_exit, "unit": "Pa"},
        choking_key: {"value": P_amb_choke, "unit": "Pa"},
        "Mass Flow": {"value": mdot, "unit": "kg/s"}
    }

@router.post("/simulate", response_model=SimulationResponse)
async def simulate(request: SimulationRequest):
    """
    Receive duct configuration and boundary conditions,
    run the gas dynamics solver, and return results.
    """
    try:
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
