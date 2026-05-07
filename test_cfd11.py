import sys
import os
import json

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.models import ComponentConfig, SimulationRequest
from app.solver.gas import GasProperties
from app.solver.general_solver import GeneralSolver1D

components = [
    ComponentConfig(type="convergent", params={"d_in": 0.1, "d_out": 0.05, "length": 0.2}),
    ComponentConfig(type="divergent", params={"d_in": 0.05, "d_out": 0.1, "length": 0.4}),
    ComponentConfig(type="solid_grain", params={
        "length": 0.5, "d_h": 0.1, "rho_b": 1800, "A_b": 0.01, 
        "n": 0.4, "a_coeff": 0.005, "T_b": 300, 
        "only_mass_addition": 1, "target_mass_flow": 0
    })
]

gas = GasProperties(gamma=1.4, R=287.0)
solver = GeneralSolver1D(gas, nx=1000)

print("Running solver with solid_grain, mass_flow=0, max_iter=50000, P_amb=101325...")
res = solver.solve(components, P0_in=5000000, T0_in=600, P_amb=101325, max_iter=50000)

print("Diagnostics:", res["diagnostics"])
machs = res["mach"]
xs = res["x"]

for i in range(1, len(machs)):
    if machs[i-1] > 1.0 and machs[i] < 1.0:
        print(f"Shock detected at x = {xs[i]:.4f}, M before = {machs[i-1]:.2f}, M after = {machs[i]:.2f}")
