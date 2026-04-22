
import sys
import os
import math

sys.path.append(os.getcwd())

from app.solver.iterative_solver import solve_full_pipeline
from app.solver.gas import GasProperties
from app.models import ComponentConfig

def reproduce_cd_nozzle_bug():
    print("=== Riproduzione Bug Nozzle CD (dP = 1 Pa) ===")
    gas = GasProperties(gamma=1.4, R=287.0)
    
    P0 = 500000.0
    Pb = 499999.0
    T0 = 600.0
    
    # Geometria dello screenshot
    components = [
        ComponentConfig(type="convergent", params={"d_in": 0.1, "d_out": 0.05, "length": 0.2}),
        ComponentConfig(type="divergent", params={"d_in": 0.05, "d_out": 0.15, "length": 0.4})
    ]
    
    results, warnings, final_comps = solve_full_pipeline(components, P0, T0, Pb, gas)
    
    M_in = results[0]["M_in"]
    M_throat = results[0]["M_out"]
    M_exit = results[1]["M_out"]
    P_exit = results[1]["P_out"]
    
    print(f"M_in:     {M_in:.6f}")
    print(f"M_throat: {M_throat:.6f}")
    print(f"M_exit:   {M_exit:.6f}")
    print(f"P_exit:   {P_exit:.1f} Pa (Target: {Pb})")
    print(f"Warnings: {warnings}")
    
    if M_throat > 0.9:
        print("\nRISULTATO: BUG RIPRODOTTO. Il flusso è sonico alla gola con dP=1 Pa!")
    else:
        print("\nRISULTATO: Il flusso è correttamente subsonico.")

if __name__ == "__main__":
    reproduce_cd_nozzle_bug()
