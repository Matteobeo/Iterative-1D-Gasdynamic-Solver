#!/usr/bin/env python3
"""
Test script to analyze the case where inlet and outlet pressures are equal
"""

from flow_solver import Iterative1DFlowSolver
import numpy as np

def test_equal_pressures():
    """Test what happens when inlet and outlet pressures are the same"""
    print("=== Testing Equal Inlet and Outlet Pressures ===")

    solver = Iterative1DFlowSolver()

    # Define conditions where inlet and outlet pressures are equal
    inlet_conditions = {
        'P0': 101325.0,  # Pa (standard atmospheric)
        'T0': 288.15,    # K (standard temperature)
        'mass_flow': 1.0  # kg/s
    }

    # Simple straight duct with no area change, no friction, no heat addition
    duct_geometry = [
        {
            'length': 1.0,   # m
            'area': 0.1,     # m²
            'dA': 0.0,       # No change in area
            'friction': 0.0, # No friction
            'heat_addition': 0.0,  # No heat addition
            'diameter': 0.1    # m
        }
    ]

    outlet_pressure = 101325.0  # Same as inlet pressure

    print(f"Inlet pressure: {inlet_conditions['P0']} Pa")
    print(f"Outlet pressure: {outlet_pressure} Pa")
    print(f"Duct length: {duct_geometry[0]['length']} m")
    print(f"Duct area: {duct_geometry[0]['area']} m²")
    print()

    try:
        solution = solver.solve(inlet_conditions, duct_geometry, outlet_pressure)

        print(f"Converged: {solution.get('converged', False)}")
        print(f"Iterations: {solution.get('iterations', 0)}")
        print(f"Final mass flow: {solution.get('mass_flow', 0)} kg/s")
        print(f"Final pressure: {solution['pressure'][-1]} Pa")
        print(f"Pressure difference: {solution['pressure'][-1] - inlet_conditions['P0']} Pa")

        if 'pressure' in solution:
            print(f"Pressure profile length: {len(solution['pressure'])}")
            print(f"Pressure range: {min(solution['pressure'])} to {max(solution['pressure'])} Pa")

            # Check velocity and Mach number
            print(f"Velocity range: {min(solution['velocity'])} to {max(solution['velocity'])} m/s")
            print(f"Mach number range: {min(solution['mach_number'])} to {max(solution['mach_number'])}")

    except Exception as e:
        print(f"Error during computation: {str(e)}")

def test_what_should_happen():
    """Explain what should happen in theory"""
    print("\n=== Theoretical Analysis ===")
    print("When inlet and outlet pressures are equal in a duct with no friction, no heat addition,")
    print("and no area changes, there should be no flow (zero velocity).")
    print()
    print("This is because:")
    print("1. The pressure gradient drives the flow")
    print("2. If there's no pressure difference, there's no driving force")
    print("3. In a straight duct with no friction or heat, the flow should be stagnant")
    print()
    print("However, in computational terms, due to numerical methods and the shooting algorithm,")
    print("the solver might find a solution that approaches zero flow but not exactly zero.")

if __name__ == "__main__":
    test_equal_pressures()
    test_what_should_happen()