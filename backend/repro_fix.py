
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "app"))
# Better: add the backend directory to path
sys.path.append(os.getcwd())

from app.solver.iterative_solver import solve_full_pipeline, generate_plot_data
from app.solver.gas import GasProperties
from app.models import ComponentConfig

def test_low_pressure_crash():
    print("Testing low pressure difference scenario...")
    gas = GasProperties(gamma=1.4, R=287.0)
    
    # Define a convergent-divergent duct
    components = [
        ComponentConfig(type="convergent", params={"d_in": 0.1, "d_out": 0.05, "length": 0.5}),
        ComponentConfig(type="divergent", params={"d_in": 0.05, "d_out": 0.1, "length": 0.5})
    ]
    
    P0 = 101325.0
    T0 = 300.0
    # Extremely small pressure difference to force M -> 0
    P_amb = 101325.0 - 0.0011
    
    print(f"P0: {P0}, P_amb: {P_amb}, DeltaP: {P0 - P_amb}")
    
    try:
        results, warnings, final_comps = solve_full_pipeline(
            components=components,
            P0_in=P0,
            T0_in=T0,
            P_amb=P_amb,
            gas=gas
        )
        print("solve_full_pipeline succeeded.")
        print(f"Warnings: {warnings}")
        
        print("Generating plot data...")
        data, boundaries = generate_plot_data(final_comps, results, gas)
        print("generate_plot_data succeeded.")
        print(f"Data points: {len(data['x'])}")
        
    except Exception as e:
        print(f"CRASH DETECTED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_low_pressure_crash()
