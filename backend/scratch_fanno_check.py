"""
Full end-to-end test: does P_static increase across a Fanno duct with supersonic inlet?
"""
from app.solver.fanno import solve_fanno, fanno_pressure_ratio
from app.solver.isentropic import pressure_ratio, temperature_ratio
from app.solver.gas import GasProperties

gamma = 1.4
gas = GasProperties(gamma=gamma, R=287.0)

# === Direct Fanno solve ===
M_in = 2.0
P0_in = 500000.0  # 5 bar
T0_in = 600.0     # K
f = 0.005
L = 0.5
D_h = 0.05

res = solve_fanno(M_in, f, L, D_h, gamma)
M_out = res["M_out"]
P0_out = P0_in * res["P0_ratio"]

# Static pressures via isentropic relation
P_in = P0_in * pressure_ratio(M_in, gamma)
P_out = P0_out * pressure_ratio(M_out, gamma)

print("=== Supersonic Fanno Flow ===")
print(f"M_in  = {M_in:.4f},  M_out  = {M_out:.4f}")
print(f"P0_in = {P0_in:.0f},  P0_out = {P0_out:.0f}  (P0_ratio = {res['P0_ratio']:.4f})")
print(f"P_in  = {P_in:.0f},  P_out  = {P_out:.0f}")
print(f"P_out/P_in (from isentropic) = {P_out/P_in:.4f}")
print(f"P_ratio from solve_fanno     = {res['P_ratio']:.4f}")
print()

# Direct check: P_out/P_in from Fanno P/P* ratios
P_ratio_fanno = fanno_pressure_ratio(M_out, gamma) / fanno_pressure_ratio(M_in, gamma)
print(f"P_ratio from Fanno P/P*      = {P_ratio_fanno:.4f}")
print()

if P_out > P_in:
    print("OK CORRECT: Pressure INCREASES in supersonic Fanno flow")
else:
    print("BUG: Pressure should INCREASE in supersonic Fanno flow!")

print()

# === Now test with the pipeline ===
from app.models import ComponentConfig
from app.solver.pipeline import evaluate_component, generate_plot_data

comp = ComponentConfig(type="fanno", params={"length": L, "d_h": D_h, "f": f})
result = evaluate_component(comp, M_in, P0_in, T0_in, gas)

print("=== Pipeline evaluate_component ===")
print(f"M_in  = {result['M_in']:.4f},  M_out  = {result['M_out']:.4f}")
print(f"P0_in = {result['P0_in']:.0f},  P0_out = {result['P0_out']:.0f}")
P_in_pipe = result['P0_in'] * pressure_ratio(result['M_in'], gamma)
P_out_pipe = result['P_out']
print(f"P_in (static) = {P_in_pipe:.0f}")
print(f"P_out (static) = {P_out_pipe:.0f}")
if P_out_pipe > P_in_pipe:
    print("OK CORRECT: Pipeline shows pressure increase")
else:
    print("BUG: Pipeline shows pressure decrease!")

print()

# === Generate plot data to see intermediate points ===
results = [result]
components = [comp]
data, boundaries = generate_plot_data(components, results, gas, num_points=10)

print("=== Plot data (x, M, P) ===")
for i in range(len(data["x"])):
    print(f"  x={data['x'][i]:.3f}  M={data['mach'][i]:.4f}  P={data['pressure'][i]:.0f}  P0={data['pressure_total'][i]:.0f}")
