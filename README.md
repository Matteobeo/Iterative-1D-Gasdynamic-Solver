# GasDynamics Pro: High-Performance CFD Suite

**GasDynamics Pro** is a comprehensive one-dimensional computational fluid dynamics (CFD) solver designed to simulate steady-state compressible flow regimes within complex duct networks. It combines textbook analytical precision with advanced numerical schemes for research-grade simulations.

---

## 🚀 Key Features

- **Dual Solver Architecture**:
  - **Analytical Mode**: Uses shooting methods and exact relations (Isentropic, Fanno, Rayleigh, Normal Shock) for rapid, precise results in standard cases.
  - **BETA Mode (General Solver)**: A high-performance numerical core implementing a **Roe Flux-Difference Splitting** scheme with **Harten entropy fix**. Accelerated via **Numba JIT** for near-native performance.
- **Dynamic Flow Visualization**: Real-time particle engine with velocity clamping, compression effects, and shock accumulation logic.
- **Full SI Compliance**: All calculations and outputs (Mass Flow [kg/s], Pressure [Pa], Temperature [K]) are strictly in International System units.
- **Drag-and-Drop Interface**: Build complex pipelines (nozzles, friction ducts, heat exchangers) visually and reorder components on the fly.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.9+ / FastAPI
- **Numerical Core**: NumPy + Numba (JIT Compilation)
- **Frontend**: React / Vite / Lucide Icons
- **Charts**: Plotly.js (High-resolution spatial profiles)

---

## 🏁 Quick Start

### Windows (Recommended)
1. Ensure you have **Python 3.9+** and **Node.js** installed and added to your PATH.
2. Clone the repository.
3. Run `INSTALL_AND_START_GASFLASH.bat` to automatically install dependencies and launch the suite.
4. For subsequent runs, use `START_GASFLASH.bat`.

### Manual Setup
**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## 📐 Computational Components

| Component | Physical Model | Key Parameters |
|-----------|----------------|----------------|
| **Convergent** | Isentropic Nozzle | $d_{in}, d_{out}, L$ |
| **Divergent** | Isentropic Diffuser | $d_{in}, d_{out}, L$ |
| **Fanno Duct** | Adiabatic Flow w/ Friction | $L, D_h, f$ |
| **Rayleigh Duct** | Frictionless w/ Heat Transfer | $q [J/kg], L$ |
| **Normal Shock** | Rankine-Hugoniot Discontinuity | Captured automatically or fitted |

---

## 🧪 Advanced Diagnostics

The system monitors and warns about:
- **Numerical Divergence**: Alerts users if extreme inputs (e.g., $P > 10^7$ Pa) are entered.
- **Thermal/Frictional Choking**: Automatic detection of sonic passages.
- **Shock Placement**: Precise tracking of normal shocks in overexpanded or high-friction regimes.
- **Mass Conservation**: Residual monitoring to ensure solution validity.

---
*Developed for Academic & Engineering Research — Ad Astra.*
