#!/usr/bin/env python3
"""
Comprehensive test of the gasdynamics solver
"""

from flow_solver import Iterative1DFlowSolver
import numpy as np

def test_zero_flow_case():
    """Test the case where there should be zero flow"""
    print("=== Test 1: Zero Flow Case (Equal Pressures) ===")

    solver = Iterative1DFlowSolver()

    inlet_conditions = {
        'P0': 101325.0,  # Pa
        'T0': 288.15,    # K
        'mass_flow': 1.0  # kg/s
    }

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

    solution = solver.solve(inlet_conditions, duct_geometry, outlet_pressure)

    print(f"Converged: {solution.get('converged', False)}")
    print(f"Final mass flow: {solution.get('mass_flow', 0):.6f} kg/s")
    print(f"Final velocity: {solution['velocity'][-1]:.6f} m/s")
    print(f"Final Mach number: {solution['mach_number'][-1]:.10f}")
    print(f"Pressure difference: {solution['pressure'][-1] - inlet_conditions['P0']:.2f} Pa")

    # Check that flow is essentially zero
    velocity = solution['velocity'][-1]
    mach = solution['mach_number'][-1]

    if abs(velocity) < 0.01 and abs(mach) < 1e-5:
        print("✓ PASS: Flow is essentially zero as expected")
    else:
        print("✗ FAIL: Flow should be zero but isn't")

    print()

def test_non_zero_flow_case():
    """Test a case with pressure difference that should produce flow"""
    print("=== Test 2: Non-Zero Flow Case (Pressure Difference) ===")

    solver = Iterative1DFlowSolver()

    inlet_conditions = {
        'P0': 200000.0,  # Pa (higher pressure)
        'T0': 288.15,    # K
        'mass_flow': 1.0  # kg/s
    }

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

    outlet_pressure = 100000.0  # Lower pressure

    solution = solver.solve(inlet_conditions, duct_geometry, outlet_pressure)

    print(f"Converged: {solution.get('converged', False)}")
    print(f"Final mass flow: {solution.get('mass_flow', 0):.6f} kg/s")
    print(f"Final velocity: {solution['velocity'][-1]:.6f} m/s")
    print(f"Final Mach number: {solution['mach_number'][-1]:.10f}")
    print(f"Pressure difference: {solution['pressure'][-1] - inlet_conditions['P0']:.2f} Pa")

    # Check that flow is non-zero
    velocity = solution['velocity'][-1]
    mach = solution['mach_number'][-1]

    if abs(velocity) > 0.1 and abs(mach) > 0.01:
        print("✓ PASS: Flow is non-zero as expected")
    else:
        print("✗ FAIL: Flow should be non-zero but isn't")

    print()

def test_simple_nozzle():
    """Test a simple converging-diverging nozzle"""
    print("=== Test 3: Simple Nozzle (Converging-Diverging) ===")

    solver = Iterative1DFlowSolver()

    inlet_conditions = {
        'P0': 101325.0,  # Pa
        'T0': 288.15,    # K
        'mass_flow': 1.0  # kg/s
    }

    # Simple converging-diverging duct
    duct_geometry = [
        {
            'length': 0.5,   # m
            'area': 0.1,     # m²
            'dA': -0.02,     # Converging (decreasing area)
            'friction': 0.02, # Some friction
            'heat_addition': 0.0,  # No heat addition
            'diameter': 0.1    # m
        },
        {
            'length': 0.5,   # m
            'area': 0.12,    # m²
            'dA': 0.02,      # Diverging (increasing area)
            'friction': 0.02, # Some friction
            'heat_addition': 0.0,  # No heat addition
            'diameter': 0.1    # m
        }
    ]

    outlet_pressure = 90000.0  # Lower pressure

    solution = solver.solve(inlet_conditions, duct_geometry, outlet_pressure)

    print(f"Converged: {solution.get('converged', False)}")
    print(f"Final mass flow: {solution.get('mass_flow', 0):.6f} kg/s")
    print(f"Initial velocity: {solution['velocity'][0]:.6f} m/s")
    print(f"Final velocity: {solution['velocity'][-1]:.6f} m/s")
    print(f"Initial Mach: {solution['mach_number'][0]:.6f}")
    print(f"Final Mach: {solution['mach_number'][-1]:.6f}")

    if solution.get('converged', False):
        print("✓ PASS: Nozzle simulation completed successfully")
    else:
        print("✗ FAIL: Nozzle simulation did not converge")

    print()

if __name__ == "__main__":
    test_zero_flow_case()
    test_non_zero_flow_case()
    test_simple_nozzle()
    print("=== All Tests Complete ===")