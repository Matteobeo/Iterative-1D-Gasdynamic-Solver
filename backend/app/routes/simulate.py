from fastapi import APIRouter, HTTPException
from app.models import SimulationRequest, SimulationResponse
from app.solver.gas import GasProperties
from app.solver.iterative_solver import solve_full_pipeline, generate_plot_data

router = APIRouter()


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
            
            return SimulationResponse(
                success=True,
                warnings=["Advanced General Solver (BETA) used."] + warnings,
                data=data,
                component_boundaries=boundaries
            )

        results, warnings, split_comps = solve_full_pipeline(
            components=request.components,
            P0_in=request.P0,
            T0_in=request.T0,
            P_amb=request.P_amb,
            gas=gas
        )
        
        data, boundaries = generate_plot_data(split_comps, results, gas)
        
        return SimulationResponse(
            success=True,
            warnings=warnings,
            data=data,
            component_boundaries=boundaries
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return SimulationResponse(
            success=False,
            error=str(e),
            warnings=["Simulation failed."]
        )
