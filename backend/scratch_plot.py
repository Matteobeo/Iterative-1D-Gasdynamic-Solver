import sys
import numpy as np

# Add backend to path
sys.path.append(r"i:\GOOGLE ANTIg\Progettini\gasdynamics-sim\backend")

from app.solver.gas import GasProperties
from app.solver.isentropic import pressure_ratio

gas = GasProperties(gamma=1.4, R=287.0)

M_in = 2.0
M_out = 1.4146

P0_in = 100.0
P0_out = 66.55

num_points = 10

M_vals = np.linspace(M_in, M_out, num_points)
P0_vals = np.linspace(P0_in, P0_out, num_points)

print("Linear interpolation approach:")
for M, P0 in zip(M_vals, P0_vals):
    P = P0 * pressure_ratio(M, gas.gamma)
    print(f"M={M:.3f}, P0={P0:.3f}, P={P:.3f}")

