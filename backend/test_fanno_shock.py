import sys
sys.path.insert(0, '.')
from app.solver.fanno import *

gamma = 1.4
M_in = 2.0
fLstar_in = fanno_parameter(M_in, gamma)
print(f"M_in: {M_in}, fLstar_in: {fLstar_in}")

try:
    M_shock = find_fanno_shock_mach(M_in, 0.4, gamma)
    print(f"fLD=0.4: Shock at M_xu = {M_shock}")
except Exception as e:
    print(f"fLD=0.4 Error: {e}")

try:
    M_shock = find_fanno_shock_mach(M_in, 0.2, gamma)
    print(f"fLD=0.2: Shock at M_xu = {M_shock}")
except Exception as e:
    print(f"fLD=0.2 Error: {e}")
