import sys
import os

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), "gasdynamics-sim", "backend"))

from app.models import ComponentConfig
from app.solver.gas import GasProperties
from app.solver.iterative_solver import solve_full_pipeline, generate_plot_data

def test_user_scenario():
    gas = GasProperties(gamma=1.4, R=287.0)
    P0_in = 1000000.0  # 10 bar
    T0_in = 300.0      # 300 K
    P_amb = 101325.0   # 1 bar (low enough to allow supersonic expansion)

    # Configuration:
    # 1. Convergent: 0.1 -> 0.05
    # 2. Divergent (a): 0.05 -> 0.1 (Shock will be placed here)
    # 3. Rayleigh: D=0.1, q = ? (We will set it later)
    # 4. Divergent (b): 0.1 -> 0.15

    # We'll use a specific q that we know might cause choking or we'll adjust it.
    # Actually, let's build the components.
    
    # To simulate the shock inside Divergent (a), we'll manually split it.
    # Divergent (a) total length 0.2m. Shock at 0.1m.
    d_throat = 0.05
    d_shock = 0.075 # middle of 0.05 and 0.1
    d_inter = 0.1
    d_exit = 0.15

    components = [
        ComponentConfig(type="convergent", params={"d_in": 0.1, "d_out": d_throat, "length": 0.1}),
        ComponentConfig(type="divergent", params={"d_in": d_throat, "d_out": d_shock, "length": 0.1}),
        ComponentConfig(type="normal_shock", params={"length": 0.0}),
        ComponentConfig(type="divergent", params={"d_in": d_shock, "d_out": d_inter, "length": 0.1}),
        # Rayleigh: we need to find q such that M_out = 1.0
        # For this test, we'll use a placeholder and see if the solver handles it.
        ComponentConfig(type="rayleigh", params={"d_h": d_inter, "q": 200000.0, "length": 0.2}), 
        ComponentConfig(type="divergent", params={"d_in": d_inter, "d_out": d_exit, "length": 0.1})
    ]

    print("Running solver for scenario...")
    try:
        results, warnings, final_comps = solve_full_pipeline(components, P0_in, T0_in, P_amb, gas)
        
        print("\n--- Risultati Analisi ---")
        for i, (comp, res) in enumerate(zip(final_comps, results)):
            print(f"Componente {i} ({comp.type}): M_in={res['M_in']:.3f}, M_out={res['M_out']:.3f}")
        
        last_res = results[-1]
        print(f"\nRegime finale nel Divergente (b): {'SUPERSONICO' if last_res['M_out'] > 1.0 else 'SUBSONICO'}")
        
        for w in warnings:
            print(f"Warning: {w}")
            
    except Exception as e:
        print(f"Errore durante l'esecuzione: {e}")

if __name__ == "__main__":
    test_user_scenario()
