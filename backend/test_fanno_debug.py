"""Debug script to test Fanno flow solver, especially supersonic regime."""
import sys
sys.path.insert(0, '.')
from app.solver.fanno import *
import numpy as np

gamma = 1.4

print("="*60)
print("FANNO FLOW - Property Ratios Verification")
print("="*60)
# Reference values from standard Fanno tables (gamma=1.4):
ref = {
    0.5:  {"fLD": 1.0691, "T": 1.1429, "P": 2.1381, "P0": 1.3398, "V": 0.5345},
    1.0:  {"fLD": 0.0000, "T": 1.0000, "P": 1.0000, "P0": 1.0000, "V": 1.0000},
    2.0:  {"fLD": 0.3050, "T": 0.6667, "P": 0.4082, "P0": 1.6875, "V": 1.6330},
    3.0:  {"fLD": 0.5222, "T": 0.4286, "P": 0.2182, "P0": 4.2346, "V": 1.9640},
}

for M, expected in ref.items():
    fLD = fanno_parameter(M, gamma)
    T_r = fanno_temperature_ratio(M, gamma)
    P_r = fanno_pressure_ratio(M, gamma)
    P0_r = fanno_total_pressure_ratio(M, gamma)
    V_r = fanno_velocity_ratio(M, gamma)
    
    ok = (abs(fLD - expected["fLD"]) < 0.001 and 
          abs(T_r - expected["T"]) < 0.001 and
          abs(P_r - expected["P"]) < 0.001 and
          abs(P0_r - expected["P0"]) < 0.001 and
          abs(V_r - expected["V"]) < 0.001)
    
    status = "OK" if ok else "MISMATCH!"
    print(f"M={M:.1f}: [{status}] 4fL*/D={fLD:.4f} (exp {expected['fLD']:.4f}), "
          f"T/T*={T_r:.4f} (exp {expected['T']:.4f}), "
          f"P/P*={P_r:.4f} (exp {expected['P']:.4f})")

print()
print("="*60)
print("FANNO FLOW - solve_fanno Supersonic Tests")
print("="*60)

# Test 1: Supersonic inlet, short duct (no choking)
# M_in=2.0, 4fL*/D_in = 0.3050
# If fLD = 0.1, then fLstar_out = 0.3050 - 0.1 = 0.2050
# Expected M_out from supersonic branch with fLstar = 0.2050
M_in = 2.0
fLD_in = fanno_parameter(M_in, gamma)
fLD_duct = 0.1
fLstar_out = fLD_in - fLD_duct
print(f"\nTest 1: M_in={M_in}, fLD_duct={fLD_duct}")
print(f"  fLstar_in = {fLD_in:.4f}")
print(f"  fLstar_out = {fLstar_out:.4f}")

# What M should give this fLstar_out?
M_expected = mach_from_fanno_parameter(fLstar_out, gamma, subsonic=False)
print(f"  Expected M_out (supersonic) = {M_expected:.4f}")

# Now test via solve_fanno
# solve_fanno(M_in, f, L, D_h, gamma) where 4fL/D = 4*f*L/D_h
# We want 4fL/D = 0.1, so pick f=0.005, L=0.5, D_h=0.1 => 4*0.005*0.5/0.1 = 0.1
res = solve_fanno(2.0, 0.005, 0.5, 0.1, gamma)
print(f"  solve_fanno result: M_out={res['M_out']:.4f}, choked={res['choked']}")
print(f"  P_ratio={res['P_ratio']:.4f}, T_ratio={res['T_ratio']:.4f}, P0_ratio={res['P0_ratio']:.4f}")

# Verify: In supersonic Fanno, M should DECREASE toward 1
# So M_out should be < M_in but > 1.0 for supersonic
if res['M_out'] < M_in and res['M_out'] > 1.0:
    print("  -> CORRECT: M decreases toward 1 in supersonic Fanno")
else:
    print("  -> ERROR: M should decrease toward 1 in supersonic Fanno!")

print()

# Test 2: Supersonic, long duct that chokes
M_in = 2.0
fLD_duct = 0.4  # > fLstar_in = 0.3050, so it should choke
print(f"Test 2: M_in={M_in}, fLD_duct={fLD_duct} (should choke)")
# 4fL/D = 0.4 => f=0.005, L=2.0, D_h=0.1 => 4*0.005*2/0.1 = 0.4
res2 = solve_fanno(2.0, 0.005, 2.0, 0.1, gamma)
print(f"  solve_fanno result: M_out={res2['M_out']:.4f}, choked={res2['choked']}")
if res2['choked']:
    print("  -> CORRECT: Flow is choked")
else:
    print("  -> ERROR: Flow should be choked!")

print()

# Test 3: Verify pressure ratios make physical sense
# In supersonic Fanno: friction DECELERATES the flow (M decreases toward 1)
# Static pressure should INCREASE (since M decreases)
# Total pressure should DECREASE (irreversible friction)
print("Test 3: Physical consistency of supersonic Fanno")
M_in = 3.0
# 4fL/D = 0.2 => f=0.005, L=1.0, D_h=0.1 => 4*0.005*1/0.1 = 0.2
res3 = solve_fanno(3.0, 0.005, 1.0, 0.1, gamma)
print(f"  M_in={M_in}, M_out={res3['M_out']:.4f}")
print(f"  P_ratio (P_out/P_in) = {res3['P_ratio']:.4f} (should be > 1 for supersonic decel)")
print(f"  T_ratio (T_out/T_in) = {res3['T_ratio']:.4f} (should be > 1 for supersonic decel)")
print(f"  P0_ratio (P0_out/P0_in) = {res3['P0_ratio']:.4f} (should be < 1, total pressure loss)")

errors = []
if res3['P_ratio'] < 1.0:
    errors.append("P_ratio should be > 1 for supersonic deceleration!")
if res3['T_ratio'] < 1.0:
    errors.append("T_ratio should be > 1 for supersonic deceleration!")
if res3['P0_ratio'] > 1.0:
    errors.append("P0_ratio should be < 1 (total pressure loss)!")
if res3['M_out'] > M_in:
    errors.append("M_out should be < M_in for supersonic Fanno!")

if errors:
    for e in errors:
        print(f"  -> ERROR: {e}")
else:
    print("  -> ALL CORRECT")

print()

# Test 4: Similarly, subsonic Fanno
# In subsonic Fanno: friction ACCELERATES the flow (M increases toward 1)
# Static pressure should DECREASE (since M increases)
# Total pressure should DECREASE (irreversible friction)
print("Test 4: Physical consistency of subsonic Fanno")
M_in = 0.5
# 4fL/D = 0.5 => f=0.005, L=2.5, D_h=0.1 => 4*0.005*2.5/0.1 = 0.5
res4 = solve_fanno(0.5, 0.005, 2.5, 0.1, gamma)
print(f"  M_in={M_in}, M_out={res4['M_out']:.4f}")
print(f"  P_ratio (P_out/P_in) = {res4['P_ratio']:.4f} (should be < 1 for subsonic accel)")
print(f"  T_ratio (T_out/T_in) = {res4['T_ratio']:.4f} (should be < 1 for subsonic accel)")
print(f"  P0_ratio (P0_out/P0_in) = {res4['P0_ratio']:.4f} (should be < 1, total pressure loss)")

errors = []
if res4['P_ratio'] > 1.0:
    errors.append("P_ratio should be < 1 for subsonic acceleration!")
if res4['T_ratio'] > 1.0:
    errors.append("T_ratio should be < 1 for subsonic acceleration!")
if res4['P0_ratio'] > 1.0:
    errors.append("P0_ratio should be < 1 (total pressure loss)!")
if res4['M_out'] < M_in:
    errors.append("M_out should be > M_in for subsonic Fanno!")

if errors:
    for e in errors:
        print(f"  -> ERROR: {e}")
else:
    print("  -> ALL CORRECT")

print()

# Test 5: Inverse consistency: if we compute M_out for a given fLD,
# and then compute solve_fanno with M_in=M_out going backward, 
# we should get M_out=M_in_original... wait, Fanno is not reversible like that.
# But let's check: if M_in=2.0 and fLD gives M_out=1.5,
# then starting from M_in=1.5 with the same fLD should give M_out closer to 1.
print("Test 5: Step-by-step supersonic Fanno")
# Break a supersonic Fanno duct into two halves and check consistency
M_in = 2.0
f = 0.005
L_total = 1.0
D_h = 0.1
fLD_total = 4.0 * f * L_total / D_h
print(f"  Total: M_in={M_in}, 4fL/D={fLD_total:.4f}")

res_full = solve_fanno(M_in, f, L_total, D_h, gamma)
print(f"  Full duct: M_out = {res_full['M_out']:.6f}")

# Two halves
res_half1 = solve_fanno(M_in, f, L_total/2, D_h, gamma)
print(f"  Half 1: M_out = {res_half1['M_out']:.6f}")

res_half2 = solve_fanno(res_half1['M_out'], f, L_total/2, D_h, gamma)
print(f"  Half 2: M_out = {res_half2['M_out']:.6f}")

if abs(res_full['M_out'] - res_half2['M_out']) < 0.001:
    print("  -> CORRECT: Two halves match full duct")
else:
    print(f"  -> ERROR: Full={res_full['M_out']:.6f}, Two halves={res_half2['M_out']:.6f}")
