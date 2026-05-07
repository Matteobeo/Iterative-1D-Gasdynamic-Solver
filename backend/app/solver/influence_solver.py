import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq
from typing import List, Dict, Tuple, Any
from app.models import ComponentConfig
from app.solver.gas import GasProperties
from app.solver.isentropic import area_mach_ratio, pressure_ratio, temperature_ratio, mach_from_area_ratio
from app.solver.normal_shock import shock_relations

class InfluenceSolver:
    def __init__(self, gas: GasProperties):
        self.gas = gas
        self.k = gas.gamma
        self.cp = gas.cp
        self.R = gas.R

    def get_coeffs(self, M2):
        k = self.k
        denom = 1.0 - M2
        if abs(denom) < 1e-8: denom = 1e-8 * np.sign(denom)

        # dM2/M2 row
        cM = {
            'A': -(2 * (1 + (k - 1) / 2 * M2)) / denom,
            'Q': (1 + k * M2) / denom,
            'f': (k * M2 * (1 + (k - 1) / 2 * M2)) / denom,
            'w': (2 * (1 + k * M2) * (1 + (k - 1) / 2 * M2)) / denom
        }
        # dP/P row
        cP = {
            'A': (k * M2) / denom,
            'Q': -k * M2 / denom,
            'f': -(k * M2 * (1 + (k - 1) * M2)) / (2 * denom),
            'w': -(2 * k * M2 * (1 + (k - 1) / 2 * M2)) / denom
        }
        # dT/T row
        cT = {
            'A': ((k - 1) * M2) / denom,
            'Q': (1 - k * M2) / denom,
            'f': -(k * (k - 1) * M2**2) / (2 * denom),
            'w': -((k - 1) * M2 * (1 + k * M2)) / denom
        }
        return cM, cP, cT

    def get_forcings(self, x_loc, comp_idx, components, y):
        M2, P, T, mdot = y
        comp = components[comp_idx]
        L = max(comp.params.get('length', 1.0), 1e-6)
        
        forcing = {'A': 0.0, 'Q': 0.0, 'f': 0.0, 'w': 0.0}
        
        if comp.type in ['convergent', 'divergent']:
            d_in = comp.params['d_in']
            d_out = comp.params['d_out']
            d_x = d_in + (d_out - d_in) * (x_loc / L)
            dd_dx = (d_out - d_in) / L
            forcing['A'] = (2.0 / d_x) * dd_dx
        
        elif comp.type == 'fanno':
            d_h = comp.params['d_h']
            f = comp.params['f']
            forcing['f'] = (4.0 * f) / d_h
            
        elif comp.type == 'rayleigh':
            q_total = comp.params['q']
            forcing['Q'] = (q_total / L) / (self.cp * T)
            
        elif comp.type == 'solid_grain':
            rho_s = comp.params.get('rho_b', 1800.0)
            A_b = comp.params.get('A_b', 0.01)
            
            only_mass = comp.params.get('only_mass_addition', 0)
            if only_mass == 1:
                target_mdot = comp.params.get('target_mass_flow', 2.0)
                a_c = target_mdot / (rho_s * A_b) if (rho_s * A_b) > 0 else 0.0
                n = 0.0
            else:
                a_c = comp.params.get('a_coeff', 0.02)
                n = comp.params.get('n', 0.5)
            # dw/dx
            mdot_gen_dx = (rho_s * A_b * a_c * (max(P, 1e4)/1e6)**n) / L
            forcing['w'] = mdot_gen_dx / max(mdot, 1e-10)
            # Thermal contribution from grain
            T_b = comp.params.get('T_b', 3000.0)
            T0 = T * (1 + (self.k - 1) / 2 * M2)
            forcing['Q'] = (mdot_gen_dx / max(mdot, 1e-10)) * (self.cp * (T_b - T0)) / (self.cp * T)

        return forcing

    def integrate_segment(self, current_state, comp_idx, components, x_start, nx_pts):
        comp = components[comp_idx]
        L = max(comp.params.get('length', 1.0), 1e-6)
        
        def deriv(t, y):
            M2, P, T, mdot = y
            if M2 <= 0: M2 = 1e-10
            cM, cP, cT = self.get_coeffs(M2)
            f = self.get_forcings(t, comp_idx, components, y)
            
            dm2_dx = M2 * (cM['A']*f['A'] + cM['Q']*f['Q'] + cM['f']*f['f'] + cM['w']*f['w'])
            dp_dx  = P  * (cP['A']*f['A'] + cP['Q']*f['Q'] + cP['f']*f['f'] + cP['w']*f['w'])
            dt_dx  = T  * (cT['A']*f['A'] + cT['Q']*f['Q'] + cT['f']*f['f'] + cT['w']*f['w'])
            dmdot_dx = mdot * f['w']
            
            return [dm2_dx, dp_dx, dt_dx, dmdot_dx]

        def sonic_event(t, y): return 1.0 - y[0]
        sonic_event.terminal = True
        
        sol = solve_ivp(deriv, [0, L], current_state, 
                        t_eval=np.linspace(0, L, max(10, nx_pts)),
                        events=sonic_event, rtol=1e-8, atol=1e-10)
        return sol

    def solve_full(self, components, P0_in, T0_in, P_amb, nx=500):
        """
        Executes the solver with shooting on M_in and shock placement.
        """
        def run_sim(M_in_val, components_list):
            M2_i = M_in_val**2
            T_i = T0_in / (1 + (self.k - 1) / 2 * M2_i)
            P_i = P0_in * (T_i / T0_in)**(self.k / (self.k - 1))
            
            # Initial area
            if components_list[0].type in ['convergent', 'divergent']:
                A_i = np.pi/4 * components_list[0].params['d_in']**2
            else:
                A_i = np.pi/4 * components_list[0].params.get('d_h', 0.1)**2
            
            mdot_i = (P_i / (self.R * T_i)) * (M_in_val * np.sqrt(self.k * self.R * T_i)) * A_i
            
            curr_y = [M2_i, P_i, T_i, mdot_i]
            hist = {'x': [], 'mach': [], 'pressure': [], 'temperature': [], 'pressure_total': [], 'temperature_total': [], 'mass_flow': []}
            curr_x = 0.0
            
            for i, comp in enumerate(components_list):
                # Normal shock is zero-length, handle separately
                if comp.type == 'normal_shock':
                    M_u = np.sqrt(curr_y[0])
                    if M_u < 1.0: raise ValueError("Subsonic shock")
                    rel = shock_relations(M_u, self.k)
                    M2_d = rel['M2']**2
                    P_d = curr_y[1] * rel['P_ratio']
                    T_d = curr_y[2] * rel['T_ratio']
                    curr_y = [M2_d, P_d, T_d, curr_y[3]]
                    
                    # Record shock point
                    hist['x'].append(curr_x)
                    hist['mach'].append(rel['M2'])
                    hist['pressure'].append(P_d)
                    hist['temperature'].append(T_d)
                    T0_d = T_d * (1 + (self.k - 1) / 2 * M2_d)
                    P0_d = P_d * (T0_d / T_d)**(self.k / (self.k - 1))
                    hist['pressure_total'].append(P0_d)
                    hist['temperature_total'].append(T0_d)
                    hist['mass_flow'].append(curr_y[3])
                    continue

                sol = self.integrate_segment(curr_y, i, components_list, curr_x, nx // len(components_list))
                if not sol.success and sol.status != 1: return None
                
                for j in range(len(sol.t)):
                    M2_h, P_h, T_h, mdot_h = sol.y[:, j]
                    hist['x'].append(curr_x + sol.t[j])
                    hist['mach'].append(np.sqrt(max(M2_h, 0)))
                    hist['pressure'].append(P_h)
                    hist['temperature'].append(T_h)
                    T0_h = T_h * (1 + (self.k - 1) / 2 * M2_h)
                    P0_h = P_h * (T0_h / T_h)**(self.k / (self.k - 1))
                    hist['pressure_total'].append(P0_h)
                    hist['temperature_total'].append(T0_h)
                    hist['mass_flow'].append(mdot_h)
                
                curr_y = sol.y[:, -1]
                curr_x += max(comp.params.get('length', 1.0), 1e-6)
                
            return hist

        # --- SHOOTING LOGIC ---
        # 1. Find Choked M_in
        def check_choke(M_test):
            try:
                res = run_sim(M_test, components)
                return res is not None
            except: return False

        M_low, M_high = 1e-6, 1.0
        for _ in range(30):
            M_mid = (M_low + M_high) / 2
            if check_choke(M_mid): M_low = M_mid
            else: M_high = M_mid
        M_choked = M_low
        
        # 2. Check if subsonic or choked
        def obj_subsonic(M):
            res = run_sim(M, components)
            return res['pressure'][-1] - P_amb
        
        # Test M_choked with subsonic branch
        res_c = run_sim(M_choked, components)
        if res_c['pressure'][-1] <= P_amb:
            # Fully subsonic
            try:
                M_target = brentq(obj_subsonic, 1e-7, M_choked, xtol=1e-6)
                return run_sim(M_target, components)
            except:
                return res_c
        
        # 3. Choked Flow - Check for shock
        # Try fully supersonic branch (if possible)
        # This part requires a more complex "split_pipeline" logic if the shock is inside.
        # For the "General Solver", we will just return the choked subsonic for now 
        # or the CFD result if it fails.
        return res_c
