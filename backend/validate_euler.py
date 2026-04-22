import numpy as np
from app.solver.euler_solver import EulerSolver1D
from app.solver.gas import GasProperties
from app.models import ComponentConfig

def validate():
    print("--- GASDYNAMICS PRO v2.0 VALIDATION ---")
    gas = GasProperties() # Air: gamma=1.4, R=287
    solver = EulerSolver1D(gas, nx=200)
    
    # Test Case: Isentropic CD Nozzle (Choked)
    # Throat at middle, d_in=0.1, d_throat=0.05, d_out=0.1
    components = [
        ComponentConfig(type="convergent", params={"d_in": 0.1, "d_out": 0.05, "length": 0.5}),
        ComponentConfig(type="divergent", params={"d_in": 0.05, "d_out": 0.1, "length": 0.5})
    ]
    
    P0_in = 1000000.0 # 10 bar
    T0_in = 300.0     # 300 K
    P_amb = 101325.0  # 1 bar (ensures choked flow)
    
    print(f"Running CD Nozzle test (P0={P0_in/1e5:.1f} bar, P_amb={P_amb/1e5:.1f} bar)...")
    results = solver.solve(components, P0_in, T0_in, P_amb, max_iter=15000)
    
    x = np.array(results["x"])
    M = np.array(results["mach"])
    mdot = np.array(results["mass_flow"])
    p = np.array(results["pressure"])
    
    # 1. Mass Conservation Check
    mdot_avg = np.mean(mdot)
    mdot_err = np.abs(mdot - mdot_avg) / mdot_avg
    max_mdot_err = np.max(mdot_err)
    
    print(f"\n[TEST 1] Mass Conservation:")
    print(f"  - Average mdot: {mdot_avg:.4f} kg/s")
    print(f"  - Max Relative Error: {max_mdot_err:.2e}")
    
    if max_mdot_err < 1e-3:
        print("  RESULT: PASSED (Robust quasi-1D conservation)")
    else:
        print("  RESULT: FAILED (Check source term implementation)")

    # 2. Throat Mach Check
    # Find throat index (min area is at x=0.5)
    throat_idx = np.argmin(np.abs(x - 0.5))
    M_throat = M[throat_idx]
    
    print(f"\n[TEST 2] Throat Mach Number:")
    print(f"  - Calculated M at throat: {M_throat:.4f}")
    if abs(M_throat - 1.0) < 0.02:
        print("  RESULT: PASSED (Sonic transition at throat)")
    else:
        print("  RESULT: FAILED (A/A* consistency issue)")

    # 3. Total Pressure Loss (Subsonic sections)
    # Check P0 at exit (should be lower than P0_in due to shock or small numerical diff)
    P0_calc = np.array(results["pressure_total"])
    P0_exit = P0_calc[-1]
    print(f"\n[TEST 3] Total Pressure Audit:")
    print(f"  - Inlet P0: {P0_in/1e5:.2f} bar")
    print(f"  - Exit P0:  {P0_exit/1e5:.2f} bar")
    
    print("\nValidation Complete.")

if __name__ == "__main__":
    validate()
