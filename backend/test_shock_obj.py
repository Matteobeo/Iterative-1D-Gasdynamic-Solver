import sys
sys.path.insert(0, '.')
from app.solver.pipeline import evaluate_pipeline, split_pipeline_at_x, find_choked_inlet_mach
from app.models import ComponentConfig
from app.solver.gas import GasProperties

gas = GasProperties(gamma=1.4, R=287.058)

comps = [
    ComponentConfig(type="convergent", params={"d_in": 0.2, "d_out": 0.1, "length": 0.5}),
    ComponentConfig(type="divergent", params={"d_in": 0.1, "d_out": 0.2, "length": 1.0}),
    ComponentConfig(type="fanno", params={"d_h": 0.2, "length": 5.0, "f": 0.05})
]

P0_in = 1e5
T0_in = 300.0

M_in_choked = find_choked_inlet_mach(comps, P0_in, T0_in, gas)
print(f"Choked M_in: {M_in_choked}")

throat_x = 0.5

print("Shock at throat:")
try:
    split_comps = split_pipeline_at_x(comps, throat_x + 1e-6)
    res = evaluate_pipeline(split_comps, M_in_choked * 0.9999, P0_in, T0_in, gas, force_supersonic_divergent=True)
    print("P_out:", res[-1]["P_out"])
except Exception as e:
    print("Error:", e)
