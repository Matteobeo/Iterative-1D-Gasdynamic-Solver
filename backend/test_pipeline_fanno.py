import sys
sys.path.insert(0, '.')
from app.solver.pipeline import solve_full_pipeline
from app.models import ComponentConfig
from app.solver.gas import GasProperties

gas = GasProperties(gamma=1.4, R=287.058)

comps = [
    ComponentConfig(type="convergent", params={"d_in": 0.2, "d_out": 0.1, "length": 0.5}),
    ComponentConfig(type="divergent", params={"d_in": 0.1, "d_out": 0.2, "length": 1.0}),
    ComponentConfig(type="fanno", params={"d_h": 0.2, "length": 5.0, "f": 0.05})
]

# High backpressure, should have shock
P0_in = 1e5
T0_in = 300.0
P_amb = 8e4

res, warnings, out_comps = solve_full_pipeline(comps, P0_in, T0_in, P_amb, gas)
print("Warnings:", warnings)
for comp in out_comps:
    print(comp.type, comp.params.get("length"))
