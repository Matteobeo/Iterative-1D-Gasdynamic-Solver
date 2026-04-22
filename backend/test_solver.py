#!/usr/bin/env python3
"""
Test script to verify the flow solver implementation
"""

from flow_solver import Iterative1DFlowSolver

def test_solver_creation():
    """Test that we can create a solver instance"""
    print("Creating flow solver...")

    solver = Iterative1DFlowSolver()
    print("Solver created successfully!")

    # Test basic parameters
    print(f"Gamma: {solver.gamma}")
    print(f"Gas constant R: {solver.R}")
    print(f"Specific heat cp: {solver.cp}")
    print(f"Spatial step dx: {solver.dx}")

    return solver

def test_basic_integration():
    """Test basic integration functionality"""
    solver = test_solver_creation()

    # Define simple test conditions
    inlet_conditions = {
        'P0': 101325.0,  # Pa
        'T0': 288.15,    # K
        'mass_flow': 1.0  # kg/s
    }

    # Define simple duct geometry (one straight section)
    duct_geometry = [
        {
            'length': 1.0,   # m
            'area': 0.1,     # m²
            'dA': 0.0,       # No change in area
            'friction': 0.02, # Friction factor
            'heat_addition': 0.0,  # No heat addition
            'diameter': 0.1    # m
        }
    ]

    outlet_pressure = 100000.0  # Pa

    print("Testing basic integration...")
    try:
        solution = solver.solve(inlet_conditions, duct_geometry, outlet_pressure)
        print("Integration completed successfully!")
        print(f"Converged: {solution.get('converged', False)}")
        print(f"Iterations: {solution.get('iterations', 0)}")
        print(f"Mass flow: {solution.get('mass_flow', 0)}")

        if 'pressure' in solution:
            print(f"Pressure profile length: {len(solution['pressure'])}")
            print(f"Final pressure: {solution['pressure'][-1]}")

    except Exception as e:
        print(f"Integration failed: {str(e)}")

if __name__ == "__main__":
    test_solver_creation()
    test_basic_integration()