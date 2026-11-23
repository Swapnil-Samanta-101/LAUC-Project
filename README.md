# 2D Navier-Stokes CFD Simulator (Airfoils & Turbofan Cascades)

A high-performance, browser-accessible 2D Computational Fluid Dynamics (CFD) simulation suite written from scratch in Python 3.11 with Numba acceleration and a modern FastAPI/WebSocket HTML5 Canvas interface.

Developed for interactive exploration, aerodynamic design intuition, and physical learning across isolated airfoils, turbomachinery blade cascades, and canonical benchmark flows.

---

## 1. Architectural Overview & File Structure

```
LAUC Project/
├── solver/
│   ├── __init__.py         # Package exports
│   ├── grid.py             # Staggered MAC grid coordinate transforms & metrics
│   ├── advection.py        # Conservative donor-cell 2nd-order upwind advection (Numba)
│   ├── diffusion.py        # 2nd-order central viscous diffusion with boundary shear (Numba)
│   ├── poisson.py          # Direct 2D Spectral (FFT/DCT) & Red-Black SOR Poisson solvers
│   ├── boundary.py         # Inflow, convective outflow, slip/no-slip, periodic pitchwise BCs
│   └── ns_solver.py        # Chorin projection orchestrator, adaptive dt, Brinkman penalization
├── geometry/
│   ├── __init__.py         # Package exports
│   ├── naca.py             # NACA 4-digit airfoil generator (m, p, t, chord, AoA)
│   ├── cascade.py          # Linear cascade generator (solidity, pitch, stagger angle, inlet angle)
│   ├── penalization.py     # Signed distance field (SDF) and Brinkman volume masks
│   └── diagnostics.py      # Surface Cp, Lift/Drag integration, divergence, turning angle, loss
├── web/
│   ├── __init__.py
│   ├── server.py           # FastAPI application, WebSocket streaming engine, REST endpoints
│   └── static/
│       ├── index.html      # Responsive aerodynamic dashboard HUD
│       ├── app.js          # Hardware-accelerated canvas renderer & particle tracer
│       └── style.css       # Clean dark-mode aerospace UI
├── tests/
│   ├── __init__.py
│   ├── test_divergence.py         # Mass conservation & machine-precision divergence checks
│   ├── test_lid_driven_cavity.py  # Re=100 benchmark vs. Ghia, Ghia & Shin (1982) data
│   ├── test_cylinder_flow.py      # Re=100 Karman vortex shedding Strouhal number test
│   ├── test_naca_airfoil.py       # NACA 0012 zero-lift & linear lift slope verification
│   └── test_cascade.py            # Turbofan cascade periodicity and turning angle test
├── requirements.txt
└── README.md
```

---

## 2. Governing Equations & Numerical Method

### 2.1 Equations of Motion
The non-dimensional incompressible Navier-Stokes equations:
$$\frac{\partial \mathbf{u}}{\partial t} + (\mathbf{u} \cdot \nabla)\mathbf{u} = -\nabla p + \frac{1}{Re}\nabla^2 \mathbf{u} + \mathbf{f}_b$$
$$\nabla \cdot \mathbf{u} = 0$$

Where:
- $\mathbf{u} = (u, v)$ is the velocity vector.
- $p$ is the kinematic pressure.
- $Re = \frac{U_\infty L}{\nu}$ is the Reynolds number based on freestream velocity and airfoil chord $c=1$.
- $\mathbf{f}_b = -\frac{\chi}{\eta}\mathbf{u}$ is the Brinkman volume penalization force modeling solid obstacles.

### 2.2 Staggered Marker-and-Cell (MAC) Grid
- Pressure $p_{j, i}$ and scalar masks $\chi_{j, i}$ reside at cell centers.
- Streamwise velocity $u_{j, i}$ resides at vertical cell faces $(j, i \pm 1/2)$.
- Pitchwise velocity $v_{j, i}$ resides at horizontal cell faces $(j \pm 1/2, i)$.
- This arrangement naturally pairs velocity divergence at cell centers with pressure gradients at cell faces, preventing pressure-velocity decoupling (checkerboarding) without empirical Rhie-Chow constants.

### 2.3 Fractional-Step (Chorin Projection) Algorithm
1. **Advection & Viscous Diffusion Predictor**:
   $$\mathbf{u}^* = \mathbf{u}^n + \Delta t \left[ -(\mathbf{u} \cdot \nabla)\mathbf{u} + \frac{1}{Re}\nabla^2 \mathbf{u} \right]$$
   - Advection uses a conservative 2nd-order donor-cell upwind flux blending ($\gamma = 0.25$) to eliminate numerical dispersion while preventing unphysical numerical dissipation.
   - Diffusion uses 2nd-order central differencing with exact wall shear formulation.
2. **Brinkman Volume Penalization**:
   $$\mathbf{u}^{**} = \frac{\mathbf{u}^*}{1 + \frac{\chi \Delta t}{\eta}}$$
   With $\eta = 10^{-3}$, this unconditionally damps velocities inside solid bodies to zero without CFL time-step penalties.
3. **Pressure Poisson Solve**:
   $$\nabla^2 p^{n+1} = \frac{1}{\Delta t} \nabla \cdot \mathbf{u}^{**}$$
   Solved using a **direct Spectral Poisson Solver** combining 2D Discrete Cosine Transforms (DCT-II) and Fast Fourier Transforms (FFT) with vectorized Thomas tridiagonal elimination ($O(N \log N)$ complexity, taking ~1.2 ms on CPU for $192 \times 96$ grid).
4. **Velocity Projection**:
   $$u^{n+1} = u^{**} - \Delta t \frac{\partial p^{n+1}}{\partial x}, \quad v^{n+1} = v^{**} - \Delta t \frac{\partial p^{n+1}}{\partial y}$$
   Yielding a velocity field that satisfies $\nabla \cdot \mathbf{u}^{n+1} = 0$ to machine precision.

### 2.4 Adaptive Time Stepping
Enforces both convective CFL and viscous diffusion limits:
$$\Delta t = \min\left( CFL \frac{\min(\Delta x, \Delta y)}{\max(|\mathbf{u}|) + 10^{-6}}, \quad \sigma_{diff} \frac{Re}{2\left(\frac{1}{\Delta x^2} + \frac{1}{\Delta y^2}\right)}, \quad \Delta t_{max} \right)$$
where $CFL = 0.35$, $\sigma_{diff} = 0.8$, $\Delta t_{max} = 0.02$.

---

## 3. Installation & Run Instructions

### 3.1 Prerequisites
Python 3.10+ (tested on Python 3.11.9 on Windows).

### 3.2 Install Dependencies
```bash
pip install -r requirements.txt
```

### 3.3 Run and Stop the Web Simulator

**Quick Start (Windows):**
- **To Start**: Double-click `run.bat` to launch the Uvicorn server and automatically open the simulation dashboard at `http://127.0.0.1:8000`.
- **To Stop**: Double-click `stop.bat` to safely terminate the server and free up port 8000.

**Manual Launch (Command Line):**
Launch the FastAPI server:
```bash
python -m uvicorn web.server:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser to:
```
http://127.0.0.1:8000
```

### 3.4 Run the Automated Validation Suite
Execute the pytest suite with the local directory configuration:
```bash
python -m pytest tests/ --rootdir=. -o cache_dir=.pytest_cache -v
```

---

## 4. Web Interface & Interactive Controls

| Control | Range / Options | Description |
| :--- | :--- | :--- |
| **Simulation Mode** | Airfoil, Cascade, Cylinder, Cavity | Switches boundary conditions and physical domain setup |
| **Reynolds Number ($Re$)** | 50 to 5000 | Adjusts fluid kinematic viscosity $\nu = 1 / Re$ |
| **Angle of Attack ($\alpha$)** | -20° to +25° | Rotates airfoil about quarter-chord with instant mask regeneration |
| **NACA Code** | 4 digits (e.g. 0012, 2412, 4412, 6412) | Sets maximum camber, camber position, and thickness |
| **Cascade Stagger ($\gamma$)** | -45° to +45° | Tilts blade chord line relative to axial flow |
| **Solidity / Pitch ($s/c$)** | 0.8 to 2.5 | Pitch-to-chord ratio of repeating cascade blades |
| **Inlet Flow Angle ($\beta_1$)** | 0° to 45° | Inlet velocity vector direction ($u_{in} = \cos\beta_1, v_{in} = \sin\beta_1$) |
| **Scalar Field** | Vorticity ($\omega$), Speed, Pressure, Divergence | Selects scalar field streamed and mapped to colormap |
| **Colormap** | Viridis, Inferno, CoolWarm | Perceptually uniform visualization palettes |
| **Particle Overlay** | Toggle on/off | Advects 300 streakline particles over velocity field |

---

## 5. Verification & Benchmark Results

Automated validation suite executed via `pytest`:

| Benchmark Test | Metric / Quantity | Expected / Published | Obtained | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Lid-Driven Cavity ($Re=100$)** | Centerline $u(y)$ vs. Ghia et al. (1982) | Relative $L_2$ Error $< 5\%$ | **1.16%** ($r = 0.9999$) | **PASSED** |
| **Circular Cylinder ($Re=100$)** | Kármán shedding Strouhal number $St$ | $St \approx 0.160 - 0.170$ (Williamson 1989) | **0.1628** | **PASSED** |
| **Mass Conservation (Fluid)** | Velocity Divergence $\nabla \cdot \mathbf{u}$ | Machine Precision | **$0.00 \times 10^{-14}$** | **PASSED** |
| **Mass Conservation (Airfoil)** | RMS Divergence with Immersed Boundary | RMS $< 1.0 \times 10^{-4}$ | **$8.45 \times 10^{-5}$** | **PASSED** |
| **NACA 0012 ($\alpha = 0^\circ$)** | Lift Coefficient $C_l$ | $C_l \approx 0.000$ (Symmetric) | **$-0.0000$** | **PASSED** |
| **NACA 0012 Lift Slope** | Lift Progression ($\alpha = 0^\circ, 4^\circ, 8^\circ$) | Monotonic positive slope $dC_l/d\alpha > 0$ | $C_l = 0.00 \to 1.55 \to 3.88$ | **PASSED** |
| **Cascade Periodicity** | Pitchwise velocity continuity ($y=0$ vs $y=L_y$) | Difference $< 1.0 \times 10^{-10}$ | **$0.00 \times 10^{-14}$** | **PASSED** |
| **Cascade Turning** | Cambered Blade Flow Turning Angle $\Delta \beta$ | $\Delta \beta > 0$ | **$+1.36^\circ$** ($Y_p = 0.535$) | **PASSED** |

---

## 6. Known Limitations

1. **Laminar Scope**: The solver models 2D laminar incompressible Navier-Stokes equations. Real-world turbofan blades operate at $Re \sim 10^6$ with 3D turbulent boundary layers, secondary tip-leakage flows, and shock waves which require Reynolds-Averaged Navier-Stokes (RANS) or Large Eddy Simulation (LES).
2. **2D Approximation**: Cascade modeling assumes infinite aspect ratio blades without endwall boundary layer separation or radial crossflow.
3. **Resolution**: Real-time interactive CPU execution defaults to $192 \times 96$ and $256 \times 128$ Cartesian grids. Fine boundary layer separation bubbles at very high angles of attack require localized grid refinement.
