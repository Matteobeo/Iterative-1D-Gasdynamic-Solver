import sys
sys.path.insert(0, '.')
from app.solver.fanno import fanno_parameter

gamma = 1.4
M_sup = 2.0
M_sub = 0.577 # M_sub after normal shock at M=2.0

fL_sup = fanno_parameter(M_sup, gamma)
fL_sub = fanno_parameter(M_sub, gamma)

print(f"fL_sup: {fL_sup}")
print(f"fL_sub: {fL_sub}")
