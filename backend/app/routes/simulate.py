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
            
        if request.solver_type == "euler":
            from app.solver.euler_solver import EulerSolver1D
            solver = EulerSolver1D(gas)
            data = solver.solve(
                components=request.components,
                P0_in=request.P0,
                T0_in=request.T0,
                P_amb=request.P_amb
            )
            # Find boundaries for UI
            boundaries = [0.0]
            curr_x = 0.0
            for comp in request.components:
                curr_x += comp.params.get("length", 1.0)
                boundaries.append(curr_x)
            
            return SimulationResponse(
                success=True,
                warnings=["Advanced Euler FVM Solver used."],
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
