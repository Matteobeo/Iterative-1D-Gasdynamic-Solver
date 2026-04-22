
from flow_solver import Iterative1DFlowSolver
import numpy as np

def test_flow_with_pressure_diff():
    print("=== Testing Flow with Pressure Difference ===")
    solver = Iterative1DFlowSolver()
    
    inlet_conditions = {
        'P0': 200000.0,  # 2 bar
        'T0': 300.0,
        'mass_flow': 1.0
    }
    
    duct_geometry = [{
        'length': 2.0,
        'area': 0.01,
        'dA': 0.0,
        'friction': 0.02, # Fanno flow
        'diameter': 0.1
    }]
    
    outlet_pressure = 150000.0 # 1.5 bar
    
    solution = solver.solve(inlet_conditions, duct_geometry, outlet_pressure)
    
    print(f"Converged: {solution['converged']}")
    print(f"Iterations: {solution['iterations']}")
    print(f"Final mass flow: {solution['mass_flow']:.4f} kg/s")
    print(f"Outlet pressure: {solution['pressure'][-1]:.1f} Pa")
    print(f"Velocity range: {solution['velocity'][0]:.1f} to {solution['velocity'][-1]:.1f} m/s")

if __name__ == "__main__":
    test_flow_with_pressure_diff()
