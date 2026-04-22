
import sys
import os
import math

# Aggiungi la cartella corrente al path per trovare i moduli
sys.path.append(os.getcwd())

from app.solver.iterative_solver import solve_full_pipeline
from app.solver.gas import GasProperties
from app.models import ComponentConfig

def test_infinitesimal_gradient():
    print("=== Test Gradiente Infinitesimo (dP = 1 Pa) ===")
    gas = GasProperties(gamma=1.4, R=287.0)
    
    # Condizioni richieste
    P0 = 500000.0   # Pa
    Pb = 499999.0   # Pa (dP = 1 Pa)
    T0 = 300.0      # K
    
    # Condotto semplice (Isentropico)
    components = [
        ComponentConfig(type="convergent", params={"d_in": 0.1, "d_out": 0.1, "length": 1.0})
    ]
    
    try:
        results, warnings, final_comps = solve_full_pipeline(components, P0, T0, Pb, gas)
        
        M_in = results[0]["M_in"]
        P_out = results[-1]["P_out"]
        
        # Calcolo teorico incomprimibile: M = sqrt(2*dP / (gamma * P0))
        M_theory = math.sqrt(2 * (P0 - Pb) / (1.4 * P0))
        
        print(f"Pressione di Ristagno (P0): {P0} Pa")
        print(f"Pressione Ambiente (Pb):   {Pb} Pa")
        print(f"Delta P:                   {P0 - Pb} Pa")
        print("-" * 40)
        print(f"Numero di Mach (M_in):     {M_in:.8f}")
        print(f"Numero di Mach Teorico:    {M_theory:.8f}")
        print(f"Pressione Uscita Calc:     {P_out:.1f} Pa")
        print(f"Error Relativo Mach:       {abs(M_in - M_theory)/M_theory * 100:.4f}%")
        print(f"Warnings:                  {warnings}")
        
        if M_in < 0.01:
            print("\nESITO: IL BUG E' RISOLTO. Il sistema ha calcolato correttamente il regime subsonico lento.")
        else:
            print("\nESITO: ERRORE. Il sistema è ancora in regime di choking.")
            
    except Exception as e:
        print(f"Errore durante la simulazione: {e}")

if __name__ == "__main__":
    test_infinitesimal_gradient()
