import numpy as np
from numba import njit, prange
from typing import List, Dict, Tuple, Any
from app.models import ComponentConfig
from app.solver.gas import GasProperties

# ============================================================
# Configurazione Griglia Multi-Zona
# ============================================================
_REFINEMENT = {
    "convergent":   0.4,
    "divergent":    0.4,
    "rayleigh":     0.5,
    "solid_grain":  0.6,
    "fanno":        1.0,
    "normal_shock": 0.2,
}

def generate_multizone_mesh(components: List[ComponentConfig], nx_base: int = 1000) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    total_L = sum(c.params.get("length", 0.0) for c in components if c.type != "normal_shock")
    if total_L < 1e-12: raise ValueError("Pipeline length zero")
    dx_base = total_L / nx_base
    segments, current_x = [], 0.0
    for comp in components:
        if comp.type == "normal_shock": continue
        L = comp.params.get("length", 0.0)
        if L < 1e-12: continue
        factor = _REFINEMENT.get(comp.type, 1.0)
        n_cells = max(4, round(L / (dx_base * factor)))
        seg_int = np.linspace(current_x, current_x + L, n_cells + 1)
        segments.append(seg_int)
        current_x += L
    x_int = np.concatenate([seg if i == 0 else seg[1:] for i, seg in enumerate(segments)])
    x = 0.5 * (x_int[:-1] + x_int[1:])
    dx_arr = x_int[1:] - x_int[:-1]
    return x, x_int, dx_arr

# ============================================================
# Solutore Quasi-1D Roe/MUSCL (User Provided Logic)
# ============================================================

@njit(inline='always')
def minmod(a, b):
    if a * b <= 0: return 0.0
    return a if abs(a) < abs(b) else b

@njit(fastmath=True)
def roe_flux_numba_fixed(rhoL, uL, pL, rhoR, uR, pR, A_int, gamma):
    # Calcolo entalpia totale
    HL = (gamma * pL / ((gamma - 1) * rhoL)) + 0.5 * uL**2
    HR = (gamma * pR / ((gamma - 1) * rhoR)) + 0.5 * uR**2
    
    # Medie di Roe
    sqL, sqR = np.sqrt(rhoL), np.sqrt(rhoR)
    u_roe = (sqL * uL + sqR * uR) / (sqL + sqR)
    H_roe = (sqL * HL + sqR * HR) / (sqL + sqR)
    a_roe = np.sqrt(max((gamma - 1) * (H_roe - 0.5 * u_roe**2), 1e-12))
    
    # Flussi Euleriani (Scalari per performance Numba)
    f1L, f2L, f3L = rhoL * uL, rhoL * uL**2 + pL, rhoL * uL * HL
    f1R, f2R, f3R = rhoR * uR, rhoR * uR**2 + pR, rhoR * uR * HR
    
    # Autovalori con correzione entropica (Harten-Hyman)
    l1, l2, l3 = u_roe, u_roe + a_roe, u_roe - a_roe
    delta = 0.1 * a_roe
    al1 = abs(l1) if abs(l1) > delta else (l1**2 + delta**2) / (2 * delta)
    al2 = abs(l2) if abs(l2) > delta else (l2**2 + delta**2) / (2 * delta)
    al3 = abs(l3) if abs(l3) > delta else (l3**2 + delta**2) / (2 * delta)
    
    # Variabili di salto
    du, dp, drho = uR - uL, pR - pL, rhoR - rhoL
    rho_roe = sqL * sqR
    
    # Intensità delle onde (Strength)
    alpha1 = drho - dp / a_roe**2
    alpha2 = (dp + rho_roe * a_roe * du) / (2 * a_roe**2)
    alpha3 = (dp - rho_roe * a_roe * du) / (2 * a_roe**2)
    
    # Dissipazione (proiezione degli autovettori)
    d1, d2, d3 = al1 * alpha1, al2 * alpha2, al3 * alpha3
    
    diss1 = d1 + d2 + d3
    diss2 = d1 * u_roe + d2 * (u_roe + a_roe) + d3 * (u_roe - a_roe)
    diss3 = d1 * 0.5 * u_roe**2 + d2 * (H_roe + u_roe * a_roe) + d3 * (H_roe - u_roe * a_roe)
    
    return (0.5 * (f1L + f1R) - 0.5 * diss1) * A_int, \
           (0.5 * (f2L + f2R) - 0.5 * diss2) * A_int, \
           (0.5 * (f3L + f3R) - 0.5 * diss3) * A_int

@njit(parallel=True, fastmath=True)
def cfd_core_loop(U_curr, A, A_int, f_fanning, q_heat, delta_h0, q_mode_total, D,
                  dx_arr, nx, gamma, R, max_iter, tol, P0_in, T0_in, P_amb):
    
    U_new = np.empty_like(U_curr)
    F = np.zeros((3, nx + 1))
    
    # Buffer per primitive
    rho, u, p, a = np.zeros(nx), np.zeros(nx), np.zeros(nx), np.zeros(nx)

    for it in range(max_iter):
        # 1. Update primitive variables
        for i in prange(nx):
            rho[i] = U_curr[0, i] / A[i]
            u[i]   = U_curr[1, i] / U_curr[0, i]
            p[i]   = max((gamma - 1) * (U_curr[2, i] / A[i] - 0.5 * rho[i] * u[i]**2), 1e-5)
            a[i]   = np.sqrt(gamma * p[i] / rho[i])

        # 2. Reconstructions e Fluxes
        for i in prange(nx + 1):
            if i == 0: # Inlet BC (Stagnation)
                u_ghost = u[0]
                T_in = T0_in / (1 + 0.5 * (gamma - 1) * (u_ghost/a[0])**2)
                p_in = P0_in * (T_in / T0_in)**(gamma/(gamma-1))
                rho_in = p_in / (R * T_in)
                rL, uL, pL = rho_in, u_ghost, p_in
                rR, uR, pR = rho[0], u[0], p[0]
            elif i == nx: # Outlet BC
                rL, uL, pL = rho[nx-1], u[nx-1], p[nx-1]
                # Se supersonico, estrapola. Se subsonico, impone P_amb
                pR = P_amb if u[nx-1] < a[nx-1] else p[nx-1]
                rR, uR = rho[nx-1], u[nx-1]
            else: # MUSCL 2nd order
                imm = max(0, i-2)
                rL = rho[i-1] + 0.5 * minmod(rho[i-1]-rho[imm], rho[i]-rho[i-1])
                uL = u[i-1]   + 0.5 * minmod(u[i-1]-u[imm],     u[i]-u[i-1])
                pL = p[i-1]   + 0.5 * minmod(p[i-1]-p[imm],     p[i]-p[i-1])
                ipp = min(nx-1, i+1)
                rR = rho[i] - 0.5 * minmod(rho[ipp]-rho[i], rho[i]-rho[i-1])
                uR = u[i]   - 0.5 * minmod(u[ipp]-u[i],     u[i]-u[i-1])
                pR = p[i]   - 0.5 * minmod(p[ipp]-p[i],     p[i]-p[i-1])

            F[0,i], F[1,i], F[2,i] = roe_flux_numba_fixed(rL, uL, pL, rR, uR, pR, A_int[i], gamma)

        # 3. Time Step (CFL) - LOCAL TIME STEPPING
        # Invece di un singolo float, dt diventa un array!
        dt_local = np.empty(nx)
        for i in prange(nx):
            dt_local[i] = 0.5 * dx_arr[i] / (abs(u[i]) + a[i] + 1e-6)

        # 4. Solver Update con Sorgenti (Predictor & Point-Implicit)
        for i in prange(nx):
            dt = dt_local[i]  # <-- Usa il dt specifico di questa cella!
            
            # Step 1: Flussi Convettivi (Predictor)
            U_star_0 = U_curr[0, i] - (dt/dx_arr[i]) * (F[0, i+1] - F[0, i])
            U_star_1 = U_curr[1, i] - (dt/dx_arr[i]) * (F[1, i+1] - F[1, i])
            U_star_2 = U_curr[2, i] - (dt/dx_arr[i]) * (F[2, i+1] - F[2, i])
            
            # Step 2: Termine geometrico di pressione (Esplicito)
            dA_dx = (A_int[i+1] - A_int[i]) / dx_arr[i]
            source_p = p[i] * dA_dx
            
            # Step 3: Attrito Point-Implicit (Stabilità Assoluta)
            K_f = 0.5 * f_fanning[i] * abs(u[i]) * (np.pi * D[i]) / A[i]
            
            # Step 4: Calore (Esplicito)
            q_val = delta_h0[i] if q_mode_total[i] else q_heat[i]
            source_q = rho[i] * abs(u[i]) * q_val * A[i]

            # Step 5: Aggiornamento Finale
            U_new[0, i] = U_star_0
            U_new[1, i] = (U_star_1 + dt * source_p) / (1.0 + dt * K_f)
            U_new[2, i] = U_star_2 + dt * source_q

        # Convergence check (Robusto)
        if it > 5000 and it % 500 == 0:
            # Errore sulla massa
            err_rho = np.linalg.norm(U_new[0] - U_curr[0]) / (np.linalg.norm(U_curr[0]) + 1e-10)
            # Errore sulla quantità di moto (chiave per sentire l'attrito fin da subito)
            err_mom = np.linalg.norm(U_new[1] - U_curr[1]) / (np.linalg.norm(U_curr[1]) + 1e-10)
            
            # Prende il caso peggiore tra i due
            # if max(err_rho, err_mom) < tol: 
            #     break
                
        U_curr[:] = U_new[:]

    return U_curr, F

class GeneralSolver1D:
    def __init__(self, gas: GasProperties, nx: int = 1000):
        self.gas, self.nx, self.gamma, self.R = gas, nx, gas.gamma, gas.R

    def solve(self, components, P0_in, T0_in, P_amb, max_iter=200000, tol=1e-8):
        x, x_int, dx_arr = generate_multizone_mesh(components, nx_base=self.nx)
        nx = len(x)
        A_int, A, f_fanning, q_heat, delta_h0 = np.zeros(nx+1), np.zeros(nx), np.zeros(nx), np.zeros(nx), np.zeros(nx)
        q_mode_total, curr_x = np.zeros(nx, dtype=np.bool_), 0.0
        for comp in components:
            if comp.type == "normal_shock": continue
            L = max(comp.params.get("length", 1.0), 1e-5)
            eps = np.min(dx_arr) * 1e-3
            mask_c, mask_i = (x >= curr_x-eps) & (x <= curr_x+L+eps), (x_int >= curr_x-eps) & (x_int <= curr_x+L+eps)
            if comp.type in ["convergent", "divergent"]:
                d_in, d_out = comp.params["d_in"], comp.params["d_out"]
                A[mask_c] = np.pi/4 * (d_in + (d_out-d_in)*(x[mask_c]-curr_x)/L)**2
                A_int[mask_i] = np.pi/4 * (d_in + (d_out-d_in)*(x_int[mask_i]-curr_x)/L)**2
            else:
                d_h = comp.params.get("d_h", 0.1)
                A[mask_c], A_int[mask_i] = np.pi/4*d_h**2, np.pi/4*d_h**2
                if comp.type == "fanno": f_fanning[mask_c] = comp.params["f"] / 4.0
                elif comp.type == "rayleigh":
                    if comp.params.get("heat_mode") == "total_specific":
                        delta_h0[mask_c], q_mode_total[mask_c] = comp.params["q"]/L, True
                    else: q_heat[mask_c] = comp.params["q"]/L
            curr_x += L
        
        D, U = np.sqrt(4*A/np.pi), np.zeros((3, nx))
        rho_init, u_init = P0_in / (self.R * T0_in), 10.0
        U[0, :], U[1, :], U[2, :] = rho_init*A, rho_init*u_init*A, (P0_in/(self.gamma-1)+0.5*rho_init*u_init**2)*A
        
        U_f, F_f = cfd_core_loop(U, A, A_int, f_fanning, q_heat, delta_h0, q_mode_total, D, dx_arr, nx, self.gamma, self.R, max_iter, tol, P0_in, T0_in, P_amb)
        
        rho, u = U_f[0,:]/A, U_f[1,:]/U_f[0,:]
        p = np.maximum((self.gamma-1)*(U_f[2,:]/A - 0.5*rho*u**2), 1e-5)
        M, T = u/np.sqrt(self.gamma*p/rho), p/(rho*self.R)
        T0, P0 = T*(1+0.5*(self.gamma-1)*M**2), p*(T*(1+0.5*(self.gamma-1)*M**2)/T)**(self.gamma/(self.gamma-1))
        mdot_f = np.full(nx, np.mean(0.5*(F_f[0, :-1]+F_f[0, 1:])))
        def s(arr): return np.nan_to_num(arr, nan=0.0).tolist()
        return {"x": x.tolist(), "mach": s(M), "pressure": s(p), "pressure_total": s(P0), "temperature": s(T), "temperature_total": s(T0), "mass_flow": s(mdot_f), "diagnostics": {"choked": bool(np.max(np.abs(M)) > 0.99), "num_normal_shocks": 0}}
