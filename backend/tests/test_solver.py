import pytest
from app.solver.gas import GasProperties
from app.solver.isentropic import temperature_ratio, pressure_ratio, density_ratio
from app.solver.normal_shock import shock_relations

def test_gas_properties():
    gas = GasProperties(gamma=1.4, R=287.0)
    assert gas.gamma == 1.4
    assert gas.R == 287.0
    assert abs(gas.cp - 1004.5) < 1.0

def test_isentropic_relations():
    # At M=1, T/T0 = 0.833, P/P0 = 0.528, rho/rho0 = 0.634 for gamma=1.4
    T_ratio = temperature_ratio(1.0, 1.4)
    P_ratio = pressure_ratio(1.0, 1.4)
    rho_ratio = density_ratio(1.0, 1.4)
    
    assert abs(T_ratio - 0.8333) < 1e-3
    assert abs(P_ratio - 0.5283) < 1e-3
    assert abs(rho_ratio - 0.6339) < 1e-3

def test_normal_shock():
    # For M1 = 2.0, gamma = 1.4: M2 = 0.5774
    res = shock_relations(2.0, 1.4)
    assert abs(res["M2"] - 0.5774) < 1e-3
    assert abs(res["P_ratio"] - 4.5) < 1e-3
