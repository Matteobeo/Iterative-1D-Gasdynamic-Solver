# Iterative-1D-Gasdynamic-Solver

1D Steady-State Gas Dynamics Flow Simulator — Web Application.
This software is a one-dimensional computational fluid dynamics (CFD) solver designed to simulate steady compressible flow regimes within duct networks. The architecture is based on a hybrid approach that combines analytical relations for individual components with global numerical methods, ensuring high physical fidelity and numerical robustness.

## Architecture

- **Backend**: Python FastAPI (gas dynamics solver)
- **Frontend**: React + Vite (drag & drop UI with Plotly.js charts)

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Server runs at `http://localhost:8000`

### Frontend
```bash
cd frontend
npm install
npm run dev
```
App runs at `http://localhost:5173`

## Components

| Component | Description | Parameters |
|-----------|-------------|------------|
| Convergent | Converging duct (isentropic) | d_in, d_out, length |
| Divergent | Diverging duct (isentropic) | d_in, d_out, length |
| Fanno | Adiabatic duct with friction | length, d_h, f |
| Rayleigh | Frictionless duct with heat transfer | q, length |

## Computational Engine Update

### Problem Addressed
The previous implementation used discrete component-based calculations that failed in complex concatenated configurations, returning incorrect mass flows or "over-choked" errors because it didn't account for upstream influences like thermal choking (Rayleigh) or friction (Fanno).

### New Solution
Implemented a new **Iterative 1D Flow Solver** using:
- **Numerical Integration**: Recursive integration (Euler/Runge-Kutta 4) along spatial domain
- **Shooting Method**: Iterative adjustment of mass flow to match boundary conditions
- **Differential Equations**: Fundamental gasdynamics equations solved at each spatial step

### Key Features
- Solves continuity: dρ/ρ + dV/V + dA/A = 0
- Solves momentum: dP + ρV dV = -4f dx/(D) ρV²/2
- Solves energy: cp dT + V dV = dq
- Uses ideal gas equation: P = ρRT

### Solver Architecture
The `Iterative1DFlowSolver` class:
- Implements shooting method for boundary value problems
- Integrates flow properties step-by-step through duct segments
- Handles choking conditions properly (Mach = 1)
- Adjusts mass flow rate iteratively for convergence
- Processes complex concatenated configurations correctly

### Benefits
- Accurately computes mass flows in complex duct arrangements
- Properly handles upstream influences on flow behavior
- Eliminates "over-choked" errors in concatenated configurations
- Maintains the same API interface for frontend compatibility
