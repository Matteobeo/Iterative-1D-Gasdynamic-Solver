from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union


class ConvergentParams(BaseModel):
    d_in: float
    d_out: float
    length: float


class DivergentParams(BaseModel):
    d_in: float
    d_out: float
    length: float


class FannoParams(BaseModel):
    d_h: float
    length: float
    f: float


class RayleighParams(BaseModel):
    d_h: float
    length: float
    q: float


class SolidGrainParams(BaseModel):
    length: float      # Grain length [m]
    d_h: float         # Port hydraulic diameter [m]
    rho_b: float       # Propellant density [kg/m^3]
    A_b: float         # Initial burning area [m^2]
    n: float           # Pressure exponent (dimensionless, typically < 1)
    a_coeff: float     # Temperature coefficient
    T_b: float         # Ambient grain temperature [K]


class ComponentConfig(BaseModel):
    type: str  # "convergent", "divergent", "fanno", "rayleigh", "solid_grain"
    params: Dict[str, float]


class Diagnostics(BaseModel):
    max_mach: float
    choked: bool
    throat_index: int
    throat_x: float
    throat_mach: float
    shocks_detected: int
    shock_locations_x: List[float]
    mass_flow_mean: float
    mass_flow_variation_pct: float
    mass_flow_conserved: bool
    P0_loss_percent: float
    sub_to_sup_transitions_x: List[float]
    sup_to_sub_transitions_x: List[float]
    num_sonic_passages: int
    num_normal_shocks: int
    is_single_cd_geometry: bool
    num_throats: int
    nozzle_regime: str


class SimulationData(BaseModel):
    x: List[float]
    mach: List[float]
    pressure: List[float]
    pressure_total: List[float]
    temperature: List[float]
    temperature_total: List[float]
    mass_flow: List[float]
    diagnostics: Dict[str, Any]


class SimulationRequest(BaseModel):
    P0: float
    T0: float
    P_amb: float
    gamma: float = 1.4
    R: float = 287.0
    components: List[ComponentConfig]
    solver_type: str = "analytical" # "analytical" or "euler"


class SimulationResponse(BaseModel):
    success: bool
    warnings: List[str] = []
    error: Optional[str] = None
    data: Optional[Union[SimulationData, Dict[str, List[float]]]] = None
    shock_location: Optional[float] = None
    component_boundaries: List[float] = []
    summary: Optional[Dict[str, Any]] = None
