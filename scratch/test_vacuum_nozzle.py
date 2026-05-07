import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.solver.gas import GasProperties
from app.solver.hybrid_solver import solve_full_pipeline
from app.models import ComponentConfig

def test_nozzle():
    gas = GasProperties(gamma=1.4, R=287.05)
    components = [
        ComponentConfig(type="convergent", params={"d_in": 0.2, "d_out": 0.1, "length": 0.2}),
        ComponentConfig(type="divergent", params={"d_in": 0.1, "d_out": 0.2, "length": 0.4})
    ]
    
    P0 = 1e6
    T0 = 300
    P_amb = 0.0 # Vacuum
    
    results, warnings, final_comps = solve_full_pipeline(
        components=components,
        P0_in=P0,
        T0_in=T0,
        P_amb=P_amb,
        gas=gas,
        request_hash="test_vacuum"
    )
    
    print("Warnings:", warnings)
    
    # Check for shocks in diagnostics
    # Note: solve_hybrid returns results, warnings, components.
    # The plot data has the diagnostics.
    from app.solver.hybrid_solver import generate_plot_data
    data, boundaries, labels = generate_plot_data(final_comps, results, gas, "test_vacuum")
    
    diag = data.get("diagnostics", {})
    num_shocks = diag.get("num_normal_shocks", 0)
    print(f"Number of shocks: {num_shocks}")
    
    exit_mach = data["mach"][-1]
    print(f"Exit Mach: {exit_mach:.4f}")
    
    if num_shocks == 0:
        print("SUCCESS: No shocks detected as expected.")
    else:
        print("FAILURE: Shocks detected in vacuum expansion!")

if __name__ == "__main__":
    test_nozzle()
