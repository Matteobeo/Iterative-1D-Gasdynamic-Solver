import sys
sys.path.insert(0, '.')
from app.solver.pipeline import evaluate_pipeline, generate_plot_data
from app.models import ComponentConfig
from app.solver.gas import GasProperties

gas = GasProperties(gamma=1.4, R=287.058)

comps = [
    ComponentConfig(type="convergent", params={"d_in": 0.2, "d_out": 0.1, "length": 0.5}),
    ComponentConfig(type="divergent", params={"d_in": 0.1, "d_out": 0.2, "length": 1.0}),
    ComponentConfig(type="fanno", params={"d_h": 0.2, "length": 0.5, "f": 0.05})
]

# Choked inlet
from app.solver.pipeline import find_choked_inlet_mach
M_in_choked = find_choked_inlet_mach(comps, 1e5, 300.0, gas)
print("Choked M_in:", M_in_choked)

res = evaluate_pipeline(comps, M_in_choked * 0.9999, 1e5, 300.0, gas, force_supersonic_divergent=True)
data, bounds = generate_plot_data(comps, res, gas, num_points=10)

print("Mach:", data["mach"][-10:])
print("P:", data["pressure"][-10:])

