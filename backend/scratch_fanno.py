import sys
import numpy as np

# Add backend to path
sys.path.append(r"i:\GOOGLE ANTIg\Progettini\gasdynamics-sim\backend")

from app.solver.fanno import solve_fanno
from app.solver.gas import GasProperties

gas = GasProperties(gamma=1.4, R=287.0)

# Supersonic Fanno flow
M_in = 2.0
f = 0.005
D_h = 0.1
L = 1.0

# 4fL/D = 4 * 0.005 * 1.0 / 0.1 = 0.2
res = solve_fanno(M_in, f, L, D_h, gas.gamma)

print("M_out:", res["M_out"])
print("P_ratio (from Fanno relations directly):", res["P_ratio"])
print("P0_ratio:", res["P0_ratio"])

from app.solver.isentropic import pressure_ratio

p_in_iso = pressure_ratio(M_in, gas.gamma)
p_out_iso = pressure_ratio(res["M_out"], gas.gamma) * res["P0_ratio"]

print("P_ratio (from isentropic ratios):", p_out_iso / p_in_iso)

