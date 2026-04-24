import numpy as np
from app.solver.general_solver import GeneralSolver1D
from app.solver.gas import GasProperties
from app.models import ComponentConfig

def run_test(name, components, P0_in, T0_in, P_amb, nx=200, max_iter=15000):
    print(f"\n--- RUNNING TEST: {name} ---")
    gas = GasProperties()
    solver = GeneralSolver1D(gas, nx=nx)
    
    results = solver.solve(components, P0_in, T0_in, P_amb, max_iter=max_iter, tol=1e-10)
    
    x = np.array(results["x"])
    M = np.array(results["mach"])
    P = np.array(results["pressure"])
    P0 = np.array(results["pressure_total"])
    mdot = np.array(results["mass_flow"])
    
    # Analysis
    mdot_avg = np.mean(mdot)
    mdot_err = np.max(np.abs(mdot - mdot_avg) / mdot_avg)
    
    # P0 Analysis (for adiabatic cases)
    p0_loss = (P0[0] - P0[-1]) / P0[0]
    
    print(f"  [RESULT] Max mdot error: {mdot_err:.2e}")
    print(f"  [RESULT] Total P0 loss:  {p0_loss*100:.2f}%")
    
    return results

def validate_pro():
    # 1. TEST ISENTROPICO (NOZZLE CD)
    # Throat at x=0.5. No friction, no heat.
    comp_cd = [
        ComponentConfig(type="convergent", params={"d_in": 0.1, "d_out": 0.05, "length": 0.5}),
        ComponentConfig(type="divergent", params={"d_in": 0.05, "d_out": 0.1, "length": 0.5})
    ]
    res_cd = run_test("Isentropic CD Nozzle", comp_cd, 10e5, 300, 1e5)
    
    # 2. TEST FANNO (ATTRITO PURO)
    # Constant area pipe with friction.
    comp_fanno = [
        ComponentConfig(type="fanno", params={"d_h": 0.05, "f": 0.005, "length": 2.0})
    ]
    res_fanno = run_test("Fanno Flow (Friction)", comp_fanno, 5e5, 300, 3e5)
    
    # 3. TEST RAYLEIGH (CALORE PURO)
    # Constant area pipe with heat addition.
    comp_rayleigh = [
        ComponentConfig(type="rayleigh", params={"d_h": 0.05, "q": 1e5, "length": 1.0}) # 100 kJ/kg
    ]
    res_rayleigh = run_test("Rayleigh Flow (Heat)", comp_rayleigh, 5e5, 300, 4e5)

    print("\n--- VALIDATION PRO COMPLETED ---")
    print("Check plots for manual visual inspection (if needed).")

if __name__ == "__main__":
    validate_pro()
