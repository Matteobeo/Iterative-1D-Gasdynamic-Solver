import numpy as np
from typing import List, Dict, Tuple, Any
from app.models import ComponentConfig
from app.solver.gas import GasProperties

class EulerSolver1D:
    """
    INDUSTRY-STANDARD Area-Weighted Quasi-1D Euler Solver (v2.1 Pro)
    
    UNITS: SI (Pa, K, m, kg, s).
    FORMULATION: Conserved variables Q = [rho*A, rho*u*A, E*A].
    FRICTION: Internally uses Fanning. Set component param `friction_type='darcy'` to provide Darcy-Weisbach factor (will be auto-converted).
    HEAT (Rayleigh): default `heat_mode='power'` with q [W/kg]. Set `heat_mode='total_specific'` and pass q [J/kg] to specify total stagnation enthalpy rise across the component.
    ALGORITHM: Roe Solver + MUSCL (2nd order) + Minmod Limiter.
    
    FRICTION CONVENTIONS:
    - "fanning" (default): tau_w = f * rho * u^2 / 2
    - "darcy": tau_w = f * rho * u^2 / 8 (where f_darcy = 4 * f_fanning)
    """

    def __init__(self, gas: GasProperties, nx: int = 1000):
        self.gas = gas
        self.nx = nx
        self.gamma = gas.gamma
        self.R = gas.R
        self.cp = gas.cp
        self._warned_reflux = False # Flag for unique warning

    def _get_primitive(self, U, A):
        """Extract primitives from area-weighted conserved variables with safety floors."""
        rho = U[0] / A
        u = U[1] / np.maximum(U[0], 1e-9)
        # Pressure with floor for numerical stability
        p = (self.gamma - 1) * (U[2]/A - 0.5 * rho * u**2)
        return np.maximum(rho, 1e-6), u, np.maximum(p, 1e-5)

    def _van_leer_limiter(self, a, b):
        """Van Leer limiter for smoother transitions compared to Minmod."""
        mask = (a * b) > 0
        res = np.zeros_like(a)
        res[mask] = (2.0 * a[mask] * b[mask]) / (a[mask] + b[mask])
        return res

    def _albada_limiter(self, a, b):
        """Albada limiter for sharper shock capture than Van Leer (Optimization 5)."""
        eps = 1e-12
        mask = (a * b) > 0
        res = np.zeros_like(a)
        res[mask] = ((a[mask]**2 + eps) * b[mask] + (b[mask]**2 + eps) * a[mask]) / (a[mask]**2 + b[mask]**2 + 2 * eps)
        return res

    def _minmod_limiter(self, a, b):
        """Minmod limiter: il più diffusivo, eccellente per sopprimere le instabilità."""
        mask = (a * b) > 0
        res = np.zeros_like(a)
        res[mask] = np.sign(a[mask]) * np.minimum(np.abs(a[mask]), np.abs(b[mask]))
        return res

    def _roe_flux_vec(self, rhoL, uL, pL, rhoR, uR, pR, A_int):
        """Vectorized Area-Weighted Roe Flux with Harten Entropy Fix"""
        # Enthalpy
        HL = (self.gamma * pL / ((self.gamma - 1) * rhoL)) + 0.5 * uL**2
        HR = (self.gamma * pR / ((self.gamma - 1) * rhoR)) + 0.5 * uR**2
        
        # Roe Averages
        sqL, sqR = np.sqrt(rhoL), np.sqrt(rhoR)
        u_roe = (sqL * uL + sqR * uR) / (sqL + sqR)
        H_roe = (sqL * HL + sqR * HR) / (sqL + sqR)
        a_roe = np.sqrt(np.maximum((self.gamma - 1) * (H_roe - 0.5 * u_roe**2), 1e-12))
        
        # Fluxes (Area-Weighted)
        FL = np.array([rhoL * uL, rhoL * uL**2 + pL, rhoL * uL * HL]) * A_int
        FR = np.array([rhoR * uR, rhoR * uR**2 + pR, rhoR * uR * HR]) * A_int

        # Eigenvalues & Robust Harten Entropy Fix
        lambdas = np.array([u_roe, u_roe + a_roe, u_roe - a_roe])
        
        # Un delta fisso proporzionale alla velocità del suono garantisce 
        # viscosità sufficiente per uccidere le oscillazioni ad alta frequenza
        delta = 0.25 * a_roe 
        
        abs_lambdas = np.where(np.abs(lambdas) < delta, (lambdas**2 + delta**2)/(2 * delta), np.abs(lambdas))

        # Wave Strengths
        du, dp, drho = uR - uL, pR - pL, rhoR - rhoL
        rho_roe = sqL * sqR
        alpha = np.array([
            drho - dp / a_roe**2,
            (dp + rho_roe * a_roe * du) / (2 * a_roe**2),
            (dp - rho_roe * a_roe * du) / (2 * a_roe**2)
        ])

        # Dissipation (Area-Weighted)
        diss = np.zeros_like(FL)
        # Entropy wave
        diss[0] += abs_lambdas[0] * alpha[0]
        diss[1] += abs_lambdas[0] * alpha[0] * u_roe
        diss[2] += abs_lambdas[0] * alpha[0] * (0.5 * u_roe**2)
        
        # Acoustic waves
        for i, sign in zip([1, 2], [1, -1]):
            diss[0] += abs_lambdas[i] * alpha[i]
            diss[1] += abs_lambdas[i] * alpha[i] * (u_roe + sign * a_roe)
            diss[2] += abs_lambdas[i] * alpha[i] * (H_roe + sign * u_roe * a_roe)

        return 0.5 * (FL + FR) - 0.5 * diss * A_int

    def solve(self, components: List[ComponentConfig], P0_in: float, T0_in: float, P_amb: float, 
              max_iter: int = 50000, tol: float = 1e-7):
        
        # 1. Geometry Setup
        total_L = sum(c.params.get("length", 1.0) for c in components if c.type != "normal_shock")
        dx = total_L / self.nx
        x = np.linspace(dx/2, total_L - dx/2, self.nx)
        x_int = np.linspace(0, total_L, self.nx + 1)
        A_int = np.zeros(self.nx + 1)
        A, D, f_fanning, q_heat = np.zeros(self.nx), np.zeros(self.nx), np.zeros(self.nx), np.zeros(self.nx)
        q_mode_total = np.zeros(self.nx, dtype=bool)
        delta_h0_per_L = np.zeros(self.nx)

        curr_x = 0.0
        for comp in components:
            L = max(comp.params.get("length", 1.0), 1e-5)
            mask_c = (x >= curr_x) & (x <= curr_x + L)
            mask_i = (x_int >= curr_x) & (x_int <= curr_x + L)
            if comp.type in ["convergent", "divergent"]:
                d_in, d_out = comp.params["d_in"], comp.params["d_out"]
                A[mask_c] = np.pi/4 * (d_in + (d_out-d_in)*(x[mask_c]-curr_x)/L)**2
                A_int[mask_i] = np.pi/4 * (d_in + (d_out-d_in)*(x_int[mask_i]-curr_x)/L)**2
            else:
                d_h = comp.params["d_h"]
                A[mask_c], A_int[mask_i] = np.pi/4*d_h**2, np.pi/4*d_h**2
                if comp.type == "fanno":
                    f_val = comp.params["f"]
                    f_type = comp.params.get("friction_type", "fanning")
                    f_fanning[mask_c] = f_val / 4.0 if f_type == "darcy" else f_val
                elif comp.type == "rayleigh":
                    q_val = comp.params["q"]
                    # Forza il default a 'total_specific' (J/kg) per usare valori fisicamente realistici
                    h_mode = comp.params.get("heat_mode", "total_specific") 
                    
                    if h_mode == "total_specific":
                        delta_h0_per_L[mask_c] = q_val / L
                        q_mode_total[mask_c] = True
                    else:
                        q_heat[mask_c] = q_val / L
            curr_x += L
        D = np.sqrt(4*A/np.pi)

        # --- ESTENSIONE 3: Validazione continuita' di area ---
        curr_x_check = 0.0
        for i, comp in enumerate(components[:-1]):
            L_i = max(comp.params.get("length", 1.0), 1e-5)
            curr_x_check += L_i
            # Trova l'ultima interfaccia <= curr_x_check (lato sinistro del salto)
            idx_left_int = np.searchsorted(x_int, curr_x_check, side='right') - 1
            idx_left_int = int(np.clip(idx_left_int, 0, len(x_int)-1))
            A_left = A_int[idx_left_int]
            # Compute next component inlet area
            next_comp = components[i+1]
            if next_comp.type in ["convergent", "divergent"]:
                A_right_expected = np.pi/4 * next_comp.params["d_in"]**2
            else:
                A_right_expected = np.pi/4 * next_comp.params["d_h"]**2
            
            rel_jump = abs(A_left - A_right_expected) / max(A_left, 1e-12)
            if rel_jump > 0.01: # > 1% area jump
                print(f"WARNING: Area discontinuity at interface {i}->{i+1} "
                      f"({comp.type}->{next_comp.type}): "
                      f"A_left={A_left:.4e}, A_right={A_right_expected:.4e}, "
                      f"jump={rel_jump*100:.2f}%. This may cause spurious oscillations.")

        # 2. Initialization
        U = np.zeros((3, self.nx))
        
        # INIZIALIZZAZIONE STABILE: usa P0_in invece di P_amb
        rho_init = P0_in / (self.R * T0_in)
        U[0, :] = rho_init * A
        U[1, :] = 0.0
        U[2, :] = (P0_in / (self.gamma - 1)) * A

        U_check = U.copy()
        cfl = 0.4
        self._warned_reflux = False
        u_b_prev, p_b_prev = None, None
        
        # 3. Main Loop (Steady-state focus via Local Time Stepping)
        for it in range(max_iter):
            # Linear CFL Ramping for stability (Optimization 4)
            if it < 1000:
                current_cfl = 0.15
            else:
                current_cfl = min(cfl, 0.15 + (cfl - 0.15) * (it - 1000) / 1000)
            rho, u, p = self._get_primitive(U, A)
            a = np.sqrt(np.maximum(self.gamma * p / rho, 1e-12))

            # --- MUSCL Reconstruction (Vectorized with Minmod Limiter) ---
            UL = np.zeros((3, self.nx+1))
            UR = np.zeros((3, self.nx+1))
            
            for i, var in enumerate([rho, u, p]):
                dq = np.diff(var)
                # Limited slopes (using Minmod for extreme stability)
                s = self._minmod_limiter(dq[:-1], dq[1:])
                # Interface reconstruction
                UL[i, 1:-1] = var[:-1] + 0.5 * np.pad(s, (1, 0), mode='constant')
                UR[i, 1:-1] = var[1:] - 0.5 * np.pad(s, (0, 1), mode='constant')

            # --- Boundary Conditions (Riemann Invariants) ---
            
            # BCs - Riemann: Solve coupled system (h0, J-)
            # Robust u[0] clamping to prevent unphysical J_minus during transients
            u0_eff = max(float(u[0]), 0.0)
            a0_eff = float(a[0])
            J_minus = u0_eff - 2*a0_eff/(self.gamma-1)
            
            h0 = self.cp * T0_in
            A_q = 1/(self.gamma-1) + 2/((self.gamma-1)**2)
            B_q = 2*J_minus/(self.gamma-1)
            C_q = 0.5*J_minus**2 - h0
            disc = B_q**2 - 4*A_q*C_q
            
            if disc >= 0:
                sqrt_disc = np.sqrt(disc)
                ab_plus = (-B_q + sqrt_disc) / (2*A_q)
                ab_minus = (-B_q - sqrt_disc) / (2*A_q)
                
                # Subsonic branch selection: maximum sound speed (minimum kinetic energy)
                candidates = [v for v in (ab_plus, ab_minus) if v > 0]
                if candidates:
                    a_b = max(candidates)
                    u_b = J_minus + 2*a_b/(self.gamma-1)
                else:
                    a_b = np.sqrt(self.gamma * self.R * T0_in)
                    u_b = 0.0
            else:
                a_b = np.sqrt(self.gamma * self.R * T0_in)
                u_b = 0.0
            
            T_b = a_b**2 / (self.gamma * self.R)
            p_b = P0_in * (np.maximum(T_b, 1e-6)/T0_in)**(self.gamma/(self.gamma-1))
            rho_b = p_b / (self.R * np.maximum(T_b, 1e-6))
            
            # Inlet Damping (Relaxation) for stability during transients
            if u_b_prev is not None:
                relax = 0.1 # Damping factor
                u_b = u_b_prev * (1 - relax) + u_b * relax
                p_b = p_b_prev * (1 - relax) + p_b * relax
            u_b_prev, p_b_prev = u_b, p_b
            
            UL[:, 0], UR[:, 0] = [rho_b, u_b, p_b], [rho_b, u_b, p_b]

            # OUTLET
            # 1. Lo stato sinistro (interno) riceve la ricostruzione al bordo (primo ordine per stabilità)
            UL[:, -1] = [rho[-1], u[-1], p[-1]]
            
            # 2. Lo stato destro (ghost cell esterna)
            if u[-1] < a[-1]: # Subsonic exit: enforce P_amb with internal entropy
                s_int = p[-1] / (rho[-1]**self.gamma)
                rho_amb = (P_amb / s_int)**(1/self.gamma)
                u_amb = u[-1] if u[-1] > 0 else 0
                UR[:, -1] = [rho_amb, u_amb, P_amb]
            else: # Supersonic exit: pure extrapolation
                UR[:, -1] = UL[:, -1]
            
            # Nota: Il flusso di Roe gestirà automaticamente il regime.

            # --- Fluxes & Update ---
            F_int = self._roe_flux_vec(UL[0], UL[1], UL[2], UR[0], UR[1], UR[2], A_int)
            dt = current_cfl * dx / (np.abs(u) + a + 1e-6)
            
            # --- WELL-BALANCED Source Terms ---
            S = np.zeros((3, self.nx))
            # Well-balanced geometric source: uses pressure averages to balance area variations
            p_mid = np.zeros(self.nx)
            p_mid[1:-1] = 0.5 * (p[:-2] + p[2:]) # Central average
            p_mid[0], p_mid[-1] = p[0], p[-1]
            S[1, :] = p_mid * (A_int[1:] - A_int[:-1]) / dx 
            # Friction (Fanning)
            S[1, :] -= 2.0 * f_fanning * rho * np.abs(u) * u * A / D 
            # Heat (Rayleigh)
            S[2, :] = np.where(q_mode_total,
                               rho * np.abs(u) * delta_h0_per_L * A,
                               rho * q_heat * A)
            
            # Update Conservatives
            U = U - (dt/dx) * (F_int[:, 1:] - F_int[:, :-1]) + dt * S

            # Convergence Check
            if it % 200 == 0:
                rel_res = np.linalg.norm(U - U_check) / (np.linalg.norm(U_check) + 1e-12)
                if rel_res < tol: break 
                U_check = U.copy()

        # 4. Post-Process
        rho, u, p = self._get_primitive(U, A)
        a_f = np.sqrt(np.maximum(self.gamma * p / rho, 1e-12))
        # M conserva il segno per diagnosticare reflusso/inversioni di flusso
        M = u / a_f
        T = p / (rho * self.R)
        T0 = T * (1 + 0.5*(self.gamma-1)*M**2)
        P0 = p * (T0/np.maximum(T, 1e-6))**(self.gamma/(self.gamma-1))
        
        mdot = rho * u * A # Local mass flow for diagnostic purposes
        
        # --- ESTENSIONE 4: Diagnostica regimi di flusso ---
        diagnostics = {}
        # 1. Choking detection
        M_abs = np.abs(M)
        M_max = float(np.max(M_abs))
        diagnostics["max_mach"] = M_max
        diagnostics["choked"] = bool(M_max >= 0.99)
        
        # 2. Throat location
        i_throat = int(np.argmin(A))
        diagnostics["throat_index"] = i_throat
        diagnostics["throat_x"] = float(x[i_throat])
        diagnostics["throat_mach"] = float(M[i_throat])
        
        # 3. Shock detection (window-based to handle smeared shocks)
        window = 3
        if len(P0) > window:
            dP0_windowed = P0[:-window] - P0[window:] # drop su window celle
            shock_threshold = 0.10 * np.max(P0) # 10% drop su 3 celle = shock
            shock_mask = dP0_windowed > shock_threshold
            raw_indices = np.where(shock_mask)[0] + window // 2
            # Cluster contiguous indices into single shocks
            if len(raw_indices) > 0:
                clusters = [raw_indices[0]]
                for idx in raw_indices[1:]:
                    if idx - clusters[-1] > window:
                        clusters.append(idx)
                shock_indices = clusters
            else:
                shock_indices = []
        else:
            shock_indices = []
        
        diagnostics["shocks_detected"] = len(shock_indices)
        diagnostics["shock_locations_x"] = [float(x[i]) for i in shock_indices]

        # 4. Mass flow conservation check (robust std/mean metric)
        mdot_abs = np.abs(mdot)
        mdot_mean = float(np.mean(mdot_abs))
        mdot_std = float(np.std(mdot_abs))
        mdot_variation = mdot_std / max(mdot_mean, 1e-12)
        diagnostics["mass_flow_mean"] = mdot_mean
        diagnostics["mass_flow_variation_pct"] = float(mdot_variation * 100)
        diagnostics["mass_flow_conserved"] = bool(mdot_variation < 0.01) # < 1% std/mean
        
        # 5. Stagnation pressure loss (total)
        P0_loss_pct = float((P0[0] - P0[-1]) / P0[0] * 100) if P0[0] > 0 else 0.0
        diagnostics["P0_loss_percent"] = P0_loss_pct

        # 6. Sonic transitions detection (general, works for any geometry)
        # Identifies M<1 -> M>1 (choking) and M>1 -> M<1 (shocks)
        M_sub_to_sup_idx = np.where((M_abs[:-1] < 1.0) & (M_abs[1:] >= 1.0))[0]
        M_sup_to_sub_idx = np.where((M_abs[:-1] >= 1.0) & (M_abs[1:] < 1.0))[0]
        diagnostics["sub_to_sup_transitions_x"] = [float(x[i]) for i in M_sub_to_sup_idx]
        diagnostics["sup_to_sub_transitions_x"] = [float(x[i]) for i in M_sup_to_sub_idx]
        diagnostics["num_sonic_passages"] = int(len(M_sub_to_sup_idx))
        diagnostics["num_normal_shocks"] = int(len(M_sup_to_sub_idx))

        # Specialized classification if geometry is a single CD nozzle
        n_throats = int(np.sum((A[1:-1] < A[:-2]) & (A[1:-1] < A[2:])))
        is_single_cd = bool(A[0] > A[i_throat] and A[-1] > A[i_throat] and n_throats <= 1)
        diagnostics["is_single_cd_geometry"] = is_single_cd
        diagnostics["num_throats"] = n_throats
        if is_single_cd:
            if M_max < 0.99:
                regime = "fully_subsonic"
            elif M[i_throat] >= 0.99 and M[-1] < 1.0 and len(shock_indices) == 0:
                regime = "choked_subsonic_diverging"
            elif M[i_throat] >= 0.99 and len(shock_indices) > 0:
                regime = "shock_in_diverging"
            elif M[i_throat] >= 0.99 and M[-1] > 1.0:
                regime = "supersonic_exit"
            else:
                regime = "unclassified"
        else:
            regime = "complex_chain"
        diagnostics["nozzle_regime"] = regime
        
        # Guard: P0 should physically decrease or stay constant in adiabatic flow
        # In non-adiabatic Rayleigh, it can increase in supersonic heating.

        def s(arr): return np.nan_to_num(arr, nan=0, posinf=1e9, neginf=-1e9).tolist()
        return {
            "x": x.tolist(), "mach": s(M), "pressure": s(p), "pressure_total": s(P0),
            "temperature": s(T), "temperature_total": s(T0), "mass_flow": s(mdot),
            "diagnostics": diagnostics
        }
