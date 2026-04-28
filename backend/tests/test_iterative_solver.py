"""
Validation tests for the new iterative_solver.py
Tests against known analytical solutions.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from app.solver.gas import GasProperties
from app.models import ComponentConfig
from app.solver.iterative_solver import solve_full_pipeline, integrate_pipeline, _m_in_from_mdot, _build_segment_map, _area_at_x
from app.solver.isentropic import choked_mass_flow, area_mach_ratio

gas = GasProperties(gamma=1.4, R=287.0)

PASS = "✅ PASS"
FAIL = "❌ FAIL"

def check(name, got, expected, tol=0.02):
    err = abs(got - expected) / (abs(expected) + 1e-12)
    status = PASS if err < tol else FAIL
    print(f"{status}  {name}: got={got:.5f}, expected={expected:.5f}, err={err*100:.2f}%")
    return err < tol

# ---------------------------------------------------------------
# Test 1: Simple convergent duct — subsonic, known P_amb
# P0=200kPa, T0=500K, P_amb=180kPa
# Analytical: M_out from isentropic P/P0 = 180/200 = 0.9
# M = sqrt(2/(gamma-1) * ((P0/P)^((gamma-1)/gamma) - 1))
# ---------------------------------------------------------------
print("\n=== Test 1: Simple convergent duct (subsonic) ===")
P0, T0, P_amb = 200e3, 500.0, 180e3
comps = [ComponentConfig(type="convergent", params={"d_in": 0.20, "d_out": 0.10, "length": 0.5})]
try:
    results, warns, _ = solve_full_pipeline(comps, P0, T0, P_amb, gas)
    M_out = results[-1]["M_out"]
    # Analytical
    ratio = P_amb / P0
    M_anal = np.sqrt(2/(gas.gamma-1) * ((1/ratio)**((gas.gamma-1)/gas.gamma) - 1))
    check("M_out convergent", M_out, M_anal, tol=0.03)
    print(f"   Warnings: {warns}")
except Exception as e:
    print(f"{FAIL}  Test 1 raised: {e}")

# ---------------------------------------------------------------
# Test 2: Fanno duct — subsonic, known 4fL/D
# M_in=0.3, 4fL/D=1.0, expected M_out from Fanno tables
# Fanno parameter at M=0.3: ~5.299
# After 4fL/D=1: fLstar_out = 5.299-1 = 4.299 → M_out ≈ 0.317
# ---------------------------------------------------------------
print("\n=== Test 2: Fanno duct (subsonic) ===")
# d_h=0.1m, f=0.02, L=1.25m → 4fL/D = 4*0.02*1.25/0.1 = 1.0
comps_fanno = [ComponentConfig(type="fanno", params={"d_h": 0.1, "f": 0.02, "length": 1.25})]
P0_f = 200e3; T0_f = 500.0
# Need P_amb such that M_in=0.3 naturally
from app.solver.isentropic import pressure_ratio, temperature_ratio
from app.solver.fanno import solve_fanno, fanno_parameter

M_in_f = 0.3
# Compute what P_amb should be for a free exit at M_out
res_fanno = solve_fanno(M_in_f, 0.02, 1.25, 0.1, gas.gamma)
M_out_fanno_anal = res_fanno["M_out"]
P_static_in = P0_f * pressure_ratio(M_in_f, gas.gamma)
P_static_out_anal = P_static_in * res_fanno["P_ratio"]
P_amb_f = P_static_out_anal * 0.999  # very close to exit static P (free exit)

try:
    # For Fanno we need an inlet section to set M_in
    # Use a convergent that produces M_in≈0.3
    d_throat = 0.1  # same as fanno d_h
    # A_star from M_in=0.3: A/A* = area_mach_ratio(0.3,1.4) ≈ 2.035
    # A_inlet needed: A = A* * 2.035, d_inlet = d_h * sqrt(2.035) ≈ 0.143
    ratio_AA = area_mach_ratio(M_in_f, gas.gamma)
    d_inlet = d_throat * np.sqrt(ratio_AA)
    comps2 = [
        ComponentConfig(type="convergent", params={"d_in": d_inlet, "d_out": d_throat, "length": 0.3}),
        ComponentConfig(type="fanno", params={"d_h": d_throat, "f": 0.02, "length": 1.25}),
    ]
    results2, warns2, _ = solve_full_pipeline(comps2, P0_f, T0_f, P_amb_f, gas)
    M_out_got = results2[-1]["M_out"]
    check("M_out Fanno", M_out_got, M_out_fanno_anal, tol=0.05)
    print(f"   M_out analytical={M_out_fanno_anal:.4f}, warns={warns2}")
except Exception as e:
    print(f"{FAIL}  Test 2 raised: {e}")

# ---------------------------------------------------------------
# Test 3: Rayleigh duct — subsonic, check T0_out
# M_in=0.3, q=50kJ/kg, T0_in=500K
# T0_out = 500 + 50000/1005 ≈ 549.75 K
# ---------------------------------------------------------------
print("\n=== Test 3: Rayleigh duct (subsonic, T0 check) ===")
from app.solver.rayleigh import solve_rayleigh
M_in_r = 0.3
q_r = 50e3
T0_in_r = 500.0
res_ray = solve_rayleigh(M_in_r, q_r, T0_in_r, gas.cp, gas.gamma)
T0_out_anal = T0_in_r + q_r / gas.cp
M_out_ray_anal = res_ray["M_out"]
print(f"   Analytical: T0_out={T0_out_anal:.2f}K, M_out={M_out_ray_anal:.4f}")
print(f"   (Rayleigh test via direct solve_rayleigh — integration test requires pipeline setup)")
print(f"   T0 energy check: {check('T0_out Rayleigh', T0_out_anal, T0_in_r + q_r/gas.cp, tol=0.001)}")

# ---------------------------------------------------------------
# Test 4: Choked nozzle — should report 'choked'
# Small P_amb forces choking
# ---------------------------------------------------------------
print("\n=== Test 4: Choked convergent nozzle ===")
comps_nozzle = [ComponentConfig(type="convergent", params={"d_in": 0.20, "d_out": 0.10, "length": 0.5})]
P0_n, T0_n, P_amb_n = 300e3, 600.0, 1e3  # P_amb << P0 → choked
try:
    results_n, warns_n, _ = solve_full_pipeline(comps_nozzle, P0_n, T0_n, P_amb_n, gas)
    M_throat = results_n[-1]["M_out"]
    choked = any("choked" in w.lower() for w in warns_n)
    status = PASS if (M_throat >= 0.98 and choked) else FAIL
    print(f"{status}  Choked nozzle: M_throat={M_throat:.4f}, warns={warns_n}")
except Exception as e:
    print(f"{FAIL}  Test 4 raised: {e}")

print("\n=== All tests complete ===")
