"""
1D Flow Solver for Gasdynamics Computations
This module implements the iterative 1D flow solver using numerical integration
and shooting method to handle complex concatenated configurations.
"""

import numpy as np
from typing import List, Tuple, Dict, Optional
import math

class Iterative1DFlowSolver:
    """
    Iterative 1D Flow Solver using numerical integration and shooting method.
    Solves the fundamental gasdynamics equations along a spatial domain.
    """

    def __init__(self,
                 gamma: float = 1.4,  # Specific heat ratio
                 R: float = 287.0,    # Gas constant (J/kg·K)
                 cp: float = 1004.0,  # Specific heat at constant pressure (J/kg·K)
                 dx: float = 0.01,    # Spatial step size (m)
                 max_iterations: int = 1000,  # Maximum iterations for convergence
                 tolerance: float = 1e-6,     # Convergence tolerance
                 max_mass_flow: float = 100.0):  # Maximum mass flow for bracketing

        self.gamma = gamma
        self.R = R
        self.cp = cp
        self.dx = dx
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.max_mass_flow = max_mass_flow

        # Store solution history
        self.solution_history = []

    def solve(self,
              inlet_conditions: Dict[str, float],
              duct_geometry: List[Dict],
              outlet_pressure: float) -> Dict:
        """
        Main solving function that implements the shooting method.

        Args:
            inlet_conditions: Dictionary with P0, T0, and initial mass flow
            duct_geometry: List of duct segments with their properties
            outlet_pressure: Boundary condition at the outlet

        Returns:
            Solution dictionary with pressure, temperature, velocity, and Mach number profiles
        """
        # Initialize the solver
        P0 = inlet_conditions['P0']
        T0 = inlet_conditions['T0']
        initial_mass_flow = inlet_conditions.get('mass_flow', None)

        # If no initial mass flow is provided, calculate it
        if initial_mass_flow is None:
            # For now, we'll use a reasonable estimate
            initial_mass_flow = self.calculate_mass_flow(P0, T0, duct_geometry[0]['area'])

        # Special case: if inlet and outlet pressures are equal, we should expect no flow
        if abs(P0 - outlet_pressure) < 1e-3:
            print("Warning: Inlet and outlet pressures are equal - expecting no flow")
            mass_flow_guess = 0.0
        else:
            mass_flow_guess = initial_mass_flow

        # Set up the shooting method
        iteration = 0

        while iteration < self.max_iterations:
            # Try the current mass flow guess
            try:
                solution = self._integrate_full_system(duct_geometry, mass_flow_guess, P0, T0)

                # Check if outlet pressure matches boundary condition
                computed_outlet_pressure = solution['pressure'][-1]
                pressure_error = abs(computed_outlet_pressure - outlet_pressure)

                if pressure_error < self.tolerance:
                    solution['mass_flow'] = mass_flow_guess
                    solution['converged'] = True
                    solution['iterations'] = iteration
                    return solution

                # Adjust mass flow based on pressure error
                if computed_outlet_pressure > outlet_pressure:
                    # Computed pressure is too high (not enough pressure drop) -> Increase mass flow
                    if mass_flow_guess < 1e-7:
                        mass_flow_guess = 0.01  # Kickstart from zero
                    else:
                        mass_flow_guess *= 1.05
                else:
                    # Computed pressure is too low (too much pressure drop) -> Decrease mass flow
                    if mass_flow_guess < 1e-6:
                        mass_flow_guess = 0.0
                    else:
                        mass_flow_guess *= 0.95

                # Ensure mass flow stays within bounds (allow zero)
                mass_flow_guess = max(0.0, min(self.max_mass_flow, mass_flow_guess))

            except Exception as e:
                # If integration fails, adjust mass flow and try again
                print(f"Integration failed at iteration {iteration}: {str(e)}")
                mass_flow_guess *= 0.5  # Reduce mass flow significantly

            iteration += 1

        # If we get here, we didn't converge
        solution['mass_flow'] = mass_flow_guess
        solution['converged'] = False
        solution['iterations'] = iteration
        return solution

    def _integrate_full_system(self,
                              duct_geometry: List[Dict],
                              mass_flow: float,
                              P0: float,
                              T0: float) -> Dict:
        """
        Integrate the full system through all duct segments.
        """
        # Calculate total length
        total_length = sum(seg['length'] for seg in duct_geometry)
        num_points = int(total_length / self.dx) + 1

        # Initialize arrays to store solution
        pressure = np.zeros(num_points)
        temperature = np.zeros(num_points)
        velocity = np.zeros(num_points)
        mach_number = np.zeros(num_points)
        density = np.zeros(num_points)
        area = np.zeros(num_points)
        length = np.zeros(num_points)

        # Initial conditions at first point
        pressure[0] = P0
        temperature[0] = T0
        density[0] = P0 / (self.R * T0)
        area_init = duct_geometry[0]['area']
        velocity[0] = mass_flow / (density[0] * area_init)
        mach_number[0] = velocity[0] / math.sqrt(self.gamma * self.R * T0)
        length[0] = 0.0

        # Store area values
        cumulative_length = 0.0
        for i, segment in enumerate(duct_geometry):
            segment_start = int(cumulative_length / self.dx)
            segment_end = int((cumulative_length + segment['length']) / self.dx)
            segment_end = min(segment_end, num_points - 1)

            # Set area for this segment
            for j in range(segment_start, segment_end + 1):
                area[j] = segment['area']

            cumulative_length += segment['length']

        # Integration through each segment
        current_state = {
            'pressure': pressure[0],
            'temperature': temperature[0],
            'velocity': velocity[0],
            'density': density[0],
            'mach_number': mach_number[0],
            'area': area[0],
            'length': length[0]
        }

        # Integrate step by step
        for i in range(1, num_points):
            # Get current segment properties
            current_area = area[i]
            current_length = i * self.dx

            # Determine which segment we're in
            current_segment = self._find_segment(duct_geometry, current_length)

            # Integrate using Runge-Kutta 4 method
            new_state = self._runge_kutta_step(current_state, current_segment, mass_flow)

            # Store results
            pressure[i] = new_state['pressure']
            temperature[i] = new_state['temperature']
            velocity[i] = new_state['velocity']
            density[i] = new_state['density']
            mach_number[i] = new_state['mach_number']
            length[i] = current_length

            # Update current state for next iteration
            current_state = new_state

            # Check for choking conditions
            if self._check_choking_conditions(current_state, current_segment):
                # Se siamo in un divergente e siamo vicini a M=1, proviamo a passare al ramo supersonico
                # invece di interrompere l'integrazione (Logica di Gola Termica/Geometrica)
                if current_segment.get('dA', 0) > 0 and abs(current_state['mach_number'] - 1.0) < 0.05:
                    current_state['mach_number'] = 1.001 
                    current_state['velocity'] = current_state['mach_number'] * math.sqrt(self.gamma * self.R * current_state['temperature'])
                    continue
                
                print(f"Choking detected at position {current_length}")
                break

        return {
            'pressure': pressure,
            'temperature': temperature,
            'velocity': velocity,
            'mach_number': mach_number,
            'density': density,
            'area': area,
            'length': length
        }

    def _runge_kutta_step(self,
                         state: Dict,
                         segment: Dict,
                         mass_flow: float) -> Dict:
        """
        Perform a single Runge-Kutta 4 step integration.
        """
        # Extract current state
        P = state['pressure']
        T = state['temperature']
        V = state['velocity']
        rho = state['density']
        A = state['area']
        x = state['length']

        # Calculate properties at current point
        Mach = V / math.sqrt(self.gamma * self.R * T)

        # Calculate derivatives using the differential equations
        dP_dx, dT_dx, dV_dx = self._calculate_derivatives(P, T, V, rho, Mach, segment, mass_flow)

        # RK4 integration - simplified version
        # In a full implementation, we'd compute k1, k2, k3, k4 properly
        P_new = P + dP_dx * self.dx
        T_new = T + dT_dx * self.dx
        V_new = V + dV_dx * self.dx

        # Recalculate density from new pressure and temperature
        rho_new = P_new / (self.R * T_new)

        # Calculate new Mach number
        Mach_new = V_new / math.sqrt(self.gamma * self.R * T_new)

        return {
            'pressure': P_new,
            'temperature': T_new,
            'velocity': V_new,
            'density': rho_new,
            'mach_number': Mach_new,
            'area': A,
            'length': x + self.dx
        }

    def _calculate_derivatives(self, P: float, T: float, V: float, rho: float,
                              Mach: float, segment: Dict, mass_flow: float) -> Tuple[float, float, float]:
        """
        Calculate the derivatives dP/dx, dT/dx, dV/dx using the differential equations.
        """
        # Get segment properties
        area = segment['area']
        dA_dx = segment.get('dA', 0.0)  # Change in area per unit length
        friction = segment.get('friction', 0.0)  # Friction factor (4f)
        dq_dx = segment.get('heat_addition', 0.0)  # Heat added per unit length
        diameter = segment.get('diameter', 1.0)

        # Numerical stability check for zero velocity
        if abs(V) < 1e-10:
            return 0.0, 0.0, 0.0

        # Speed of sound squared
        a2 = self.gamma * self.R * T
        
        # Influence coefficient for Mach number and velocity
        # (1-M^2) * dV/V = -dA/A + (gamma*M^2/2) * (4f*dx/D) + (gamma-1)/(a^2) * dq
        term_area = -dA_dx / area
        term_friction = (self.gamma * Mach**2 / 2.0) * (friction / diameter)
        term_heat = (self.gamma - 1.0) / a2 * dq_dx
        
        # Solve for dV_dx
        denom = (1.0 - Mach**2)
        if abs(denom) < 1e-4:
            denom = 1e-4 * np.sign(denom) if denom != 0 else 1e-4
            
        dV_dx = (V / denom) * (term_area + term_friction + term_heat)

        # Momentum equation: dP = -rho * V * dV - (4f * dx/D) * (rho * V^2 / 2)
        dP_dx = -rho * V * dV_dx - (friction / diameter) * (rho * V**2 / 2.0)

        # Energy equation: cp * dT + V * dV = dq
        dT_dx = (dq_dx - V * dV_dx) / self.cp

        return dP_dx, dT_dx, dV_dx

        return dP_dx, dT_dx, dV_dx

    def _check_choking_conditions(self,
                                current_state: Dict,
                                segment: Dict) -> bool:
        """
        Check if choking conditions are met.

        Args:
            current_state: Current flow state
            segment: Current segment properties

        Returns:
            True if choking condition is detected
        """
        Mach = current_state['mach_number']

        # Check if Mach number reaches 1 (choking)
        if abs(Mach - 1.0) < 1e-3:
            # Se siamo in una sezione con variazione di area positiva (divergente),
            # questo potrebbe essere un punto di gola (geometrica o termica).
            # Non blocchiamo subito l'integrazione per permettere il test del ramo supersonico.
            if segment.get('dA', 0) > 0:
                return False 
            
            # Altrimenti è un vero blocco (es. Mach 1 in un convergente senza gola)
            return True

        return False

    def _find_segment(self, duct_geometry: List[Dict], length: float) -> Dict:
        """
        Find which segment contains a given length.
        """
        cumulative_length = 0.0
        for segment in duct_geometry:
            if length <= cumulative_length + segment['length']:
                return segment
            cumulative_length += segment['length']
        return duct_geometry[-1]  # Return last segment if out of bounds

    def calculate_mass_flow(self,
                           P0: float,
                           T0: float,
                           A: float) -> float:
        """
        Calculate mass flow rate based on stagnation conditions.

        Args:
            P0: Stagnation pressure (Pa)
            T0: Stagnation temperature (K)
            A: Cross-sectional area (m²)

        Returns:
            Mass flow rate (kg/s)
        """
        # For choked flow (Mach = 1)
        # mdot = P0 * A * sqrt(gamma / R / T0) * (2 / (gamma + 1))^( (gamma + 1) / (2 * (gamma - 1)) )

        # For now, using a simplified approach
        rho0 = P0 / (self.R * T0)
        c0 = math.sqrt(self.gamma * self.R * T0)
        mass_flow = rho0 * A * c0  # This is a rough estimate

        return mass_flow

# Differential equation system functions
def continuity_equation(density: float, velocity: float, area: float) -> float:
    """
    Continuity equation: dρ/ρ + dV/V + dA/A = 0

    This equation ensures mass conservation in the flow.

    Physical meaning:
    - The change in density divided by density + change in velocity divided by velocity + change in area divided by area = 0
    - This means that mass flow rate is constant along the duct

    Practical consequence:
    - In converging sections (dA < 0), if flow is subsonic (M < 1), velocity increases
    - In diverging sections (dA > 0), if flow is subsonic, velocity decreases
    - In converging sections (dA < 0), if flow is supersonic (M > 1), velocity decreases
    - In diverging sections (dA > 0), if flow is supersonic, velocity increases

    Example in aerospace:
    - In a converging-diverging nozzle, the throat (dA = 0) is where Mach = 1
    - The continuity equation ensures that mass flow rate is the same at all cross-sections
    """
    pass

def momentum_equation(dP: float, density: float, velocity: float,
                     friction_factor: float, diameter: float) -> float:
    """
    Momentum equation: dP + ρV dV = -4f dx/(D) ρV²/2

    This equation represents the balance of forces acting on the fluid element.

    Physical meaning:
    - Pressure change + density × velocity × velocity change = frictional loss term
    - The left side represents pressure and momentum changes
    - The right side represents frictional losses along the duct

    Practical consequence:
    - Friction causes pressure drop along the duct
    - The frictional term is proportional to velocity squared
    - This is crucial for calculating pressure recovery in ducts

    Example in aerospace:
    - In a combustion chamber, friction losses reduce the total pressure
    - In a turbine inlet duct, pressure losses affect overall engine efficiency
    - The momentum equation helps calculate pressure distribution along the flow path
    """
    pass

def energy_equation(dT: float, specific_heat: float, velocity: float,
                   heat_added: float) -> float:
    """
    Energy equation: cp dT + V dV = dq

    This equation represents the conservation of energy in the flow.

    Physical meaning:
    - Specific heat capacity × temperature change + velocity × velocity change = heat added
    - This accounts for both sensible heat (temperature change) and kinetic energy changes

    Practical consequence:
    - Heat addition increases temperature and can change Mach number
    - In Rayleigh flow, heat addition can cause choking at the throat
    - This equation is essential for calculating temperature distribution in heated flows

    Example in aerospace:
    - In a combustor, heat addition increases temperature and can accelerate flow to supersonic speeds
    - In a turbine, heat removal affects temperature distribution
    - The energy equation is fundamental in calculating thermal efficiency of propulsion systems
    """
    pass

def ideal_gas_equation(pressure: float, density: float, gas_constant: float,
                     temperature: float) -> float:
    """
    Ideal gas equation: P = ρRT

    This is the equation of state for an ideal gas.

    Physical meaning:
    - Pressure = density × gas constant × temperature
    - This relates the thermodynamic properties of the gas
    - It allows conversion between pressure, density, and temperature

    Practical consequence:
    - Allows calculation of one thermodynamic property if others are known
    - Essential for calculating density from pressure and temperature
    - Forms the basis for all other thermodynamic calculations

    Example in aerospace:
    - In a rocket engine, knowing pressure and temperature allows calculation of density
    - In computational fluid dynamics, this equation is used to close the system of equations
    - It's fundamental in calculating gas properties at different points in a propulsion system
    """
    pass