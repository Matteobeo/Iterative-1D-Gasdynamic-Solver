import sys
import numpy as np

# Add backend to path
sys.path.append(r"i:\GOOGLE ANTIg\Progettini\gasdynamics-sim\backend")

from app.solver.pipeline import evaluate_pipeline, generate_plot_data, find_choked_inlet_mach
from app.models import ComponentConfig
from app.solver.gas import GasProperties

gas = GasProperties(gamma=1.4, R=287.058)

comps = [
    ComponentConfig(type="divergent", params={"d_in": 0.05, "d_out": 0.15, "length": 0.4}),
    ComponentConfig(type="fanno", params={"d_h": 0.05, "length": 1.0, "f": 0.005})
]

P0_in = 500000.0
T0_in = 300.0

# Divergent nozzle as first component typically implies choked inlet if we force supersonic
M_in_choked = find_choked_inlet_mach(comps, P0_in, T0_in, gas)
print("Choked M_in:", M_in_choked)

res = evaluate_pipeline(comps, M_in_choked * 0.9999, P0_in, T0_in, gas, force_supersonic_divergent=True)

for i, r in enumerate(res):
    print(f"Comp {i}: M_in={r['M_in']:.3f}, M_out={r['M_out']:.3f}, P_out={r['P_out']:.3f}")

data, bounds = generate_plot_data(comps, res, gas, num_points=20)

for x, m, p, p0 in zip(data["x"], data["mach"], data["pressure"], data["pressure_total"]):
    if x >= 0.4:
        print(f"x={x:.3f}, M={m:.3f}, P={p:.3f}, P0={p0:.3f}")

