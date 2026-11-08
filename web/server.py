"""FastAPI WebSocket server for real-time 2D Navier-Stokes CFD simulation.

Streams simulation frames, telemetry, and aerodynamic forces to the browser
via persistent WebSocket connection with non-blocking execution.
"""

import os
import sys
import asyncio
import base64
from typing import Dict, Any, List, Optional
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from solver.grid import MACGrid
from solver.boundary import BoundaryConditions
from solver.ns_solver import NavierStokesSolver
from geometry.naca import NACA4Airfoil
from geometry.cascade import TurbofanCascade
from geometry.penalization import compute_polygon_mask, compute_circle_mask
from geometry.diagnostics import AerodynamicDiagnostics

app = FastAPI(title="2D Navier-Stokes CFD Simulator")

# Static files path
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SimConfig(BaseModel):
    mode: str = "airfoil"  # "airfoil", "cascade", "cylinder", "cavity"
    naca_code: str = "0012"
    alpha_deg: float = 4.0
    reynolds: float = 500.0
    resolution: str = "standard"  # "fast" (128x64), "standard" (192x96), "high" (256x128)
    display_field: str = "vorticity"  # "vorticity", "speed", "pressure", "divergence"
    # Cascade options
    cascade_pitch: float = 1.5
    cascade_stagger: float = 25.0
    cascade_inlet_angle: float = 25.0
    cascade_camber: str = "6412"


class SimulationManager:
    """Manages active CFD simulation state and physics stepping loop."""

    def __init__(self) -> None:
        self.config = SimConfig()
        self.running: bool = True
        self.step_once: bool = False
        self.grid: Optional[MACGrid] = None
        self.solver: Optional[NavierStokesSolver] = None
        self.polygons: List[np.ndarray] = []
        self.lock = asyncio.Lock()
        self.setup_simulation()

    def _get_grid_dims(self) -> tuple[int, int, float, float]:
        if self.config.resolution == "fast":
            nx, ny = 128, 64
        elif self.config.resolution == "high":
            nx, ny = 256, 128
        else:  # standard
            nx, ny = 192, 96

        if self.config.mode == "cavity":
            return nx, ny, 1.0, 1.0
        elif self.config.mode == "cylinder":
            return nx, ny, 8.0, 4.0
        elif self.config.mode == "cascade":
            return nx, ny, 6.0, 3.0
        else:  # airfoil
            return nx, ny, 6.0, 3.0

    def setup_simulation(self) -> None:
        """Initialize or rebuild the CFD solver according to current config."""
        nx, ny, lx, ly = self._get_grid_dims()
        self.grid = MACGrid(nx=nx, ny=ny, lx=lx, ly=ly)
        self.polygons = []

        if self.config.mode == "cavity":
            bc = BoundaryConditions(inlet_type="no_slip", outlet_type="no_slip", top_bottom_type="lid", u_lid=1.0)
            self.solver = NavierStokesSolver(grid=self.grid, re=self.config.reynolds, boundary_conditions=bc)
            self.solver.reset_flow(0.0, 0.0)

        elif self.config.mode == "cylinder":
            bc = BoundaryConditions(inlet_type="uniform_inlet", outlet_type="convective", top_bottom_type="free_slip")
            self.solver = NavierStokesSolver(grid=self.grid, re=self.config.reynolds, boundary_conditions=bc)
            d = 0.6
            mask = compute_circle_mask(center_x=2.0, center_y=2.0, radius=d / 2.0, X=self.grid.X_c, Y=self.grid.Y_c)
            self.solver.set_solid_mask(mask)
            # Add small wake perturbation to initiate shedding
            self.solver.v += 0.1 * np.exp(-((self.grid.X_v - 2.5) ** 2 + (self.grid.Y_v - 2.2) ** 2) / 0.2)

        elif self.config.mode == "cascade":
            u_in = float(np.cos(np.radians(self.config.cascade_inlet_angle)))
            v_in = float(np.sin(np.radians(self.config.cascade_inlet_angle)))
            bc = BoundaryConditions(
                inlet_type="uniform_inlet",
                outlet_type="convective",
                top_bottom_type="periodic",
                u_inlet=u_in,
                v_inlet=v_in
            )
            self.solver = NavierStokesSolver(grid=self.grid, re=self.config.reynolds, boundary_conditions=bc)
            cascade = TurbofanCascade(
                chord=1.0,
                pitch=self.config.cascade_pitch,
                stagger_deg=self.config.cascade_stagger,
                camber_code=self.config.cascade_camber,
                domain_ly=ly,
                x_axial_pos=1.5,
                inlet_flow_angle_deg=self.config.cascade_inlet_angle
            )
            self.polygons = cascade.polygons
            mask = compute_polygon_mask(self.polygons, self.grid.X_c, self.grid.Y_c)
            self.solver.set_solid_mask(mask)

        else:  # airfoil
            bc = BoundaryConditions(inlet_type="uniform_inlet", outlet_type="convective", top_bottom_type="free_slip")
            self.solver = NavierStokesSolver(grid=self.grid, re=self.config.reynolds, boundary_conditions=bc)
            airfoil = NACA4Airfoil(
                code=self.config.naca_code,
                chord=1.0,
                x_origin=1.5,
                y_origin=1.5,
                alpha_deg=self.config.alpha_deg,
                n_points=120
            )
            self.polygons = [airfoil.polygon]
            mask = compute_polygon_mask(self.polygons, self.grid.X_c, self.grid.Y_c)
            self.solver.set_solid_mask(mask)

    def step(self) -> None:
        """Advance simulation by 1 time step."""
        if self.solver is not None:
            self.solver.step()

    def get_frame_payload(self) -> Dict[str, Any]:
        """Compile optimized frame data for WebSocket client."""
        if self.solver is None or self.grid is None:
            return {}

        # 1. Extract selected scalar field
        field_type = self.config.display_field
        if field_type == "speed":
            field = self.grid.velocity_magnitude(self.solver.u, self.solver.v)
        elif field_type == "pressure":
            field = self.solver.p.copy()
        elif field_type == "divergence":
            field = self.grid.compute_divergence(self.solver.u, self.solver.v)
        else:  # vorticity
            field = self.grid.compute_vorticity(self.solver.u, self.solver.v)

        # Handle mask overlay (solid body indicated clearly)
        f_min = float(np.min(field))
        f_max = float(np.max(field))
        if abs(f_max - f_min) < 1e-6:
            f_max = f_min + 1.0

        # Normalize scalar field to uint8 (0 to 255) for ultra-fast network transmission
        norm_field = np.clip((field - f_min) / (f_max - f_min) * 255.0, 0.0, 255.0).astype(np.uint8)
        field_b64 = base64.b64encode(norm_field.tobytes()).decode("ascii")

        # 2. Downsampled velocity field for client-side particle tracers (e.g. 32x16 grid)
        skip_x = max(1, self.grid.nx // 32)
        skip_y = max(1, self.grid.ny // 16)
        u_c, v_c = self.grid.to_cell_centers(self.solver.u, self.solver.v)
        u_sub = u_c[::skip_y, ::skip_x].astype(np.float32)
        v_sub = v_c[::skip_y, ::skip_x].astype(np.float32)

        # 3. Aerodynamic forces & surface Cp
        fx, fy, cl, cd = self.solver.compute_aerodynamic_forces()
        cp_data = {}
        if self.config.mode == "airfoil":
            cp_dict = AerodynamicDiagnostics.extract_surface_cp(self.solver, x_le=1.5, chord=1.0, n_samples=35)
            cp_data = {
                "x_c": cp_dict["x_c"].tolist(),
                "cp_upper": np.round(cp_dict["cp_upper"], 3).tolist(),
                "cp_lower": np.round(cp_dict["cp_lower"], 3).tolist()
            }

        cascade_metrics = {}
        if self.config.mode == "cascade":
            cascade_metrics = AerodynamicDiagnostics.compute_cascade_metrics(self.solver)

        # 4. Polygons in normalized coordinates [0, 1] for canvas overlay
        poly_coords = []
        for poly in self.polygons:
            poly_norm = poly.copy()
            poly_norm[:, 0] /= self.grid.lx
            poly_norm[:, 1] /= self.grid.ly
            poly_coords.append(np.round(poly_norm, 4).tolist())

        return {
            "type": "frame",
            "time": round(self.solver.time, 3),
            "step": self.solver.step_count,
            "dt": round(self.solver.dt, 5),
            "nx": self.grid.nx,
            "ny": self.grid.ny,
            "lx": self.grid.lx,
            "ly": self.grid.ly,
            "f_min": round(f_min, 3),
            "f_max": round(f_max, 3),
            "field_b64": field_b64,
            "field_type": field_type,
            "cl": round(cl, 4),
            "cd": round(cd, 4),
            "max_div": f"{self.solver.max_div:.2e}",
            "rms_div": f"{self.solver.rms_div:.2e}",
            "cp_data": cp_data,
            "cascade_metrics": cascade_metrics,
            "polygons": poly_coords,
            "vel_sub": {
                "nx": u_sub.shape[1],
                "ny": u_sub.shape[0],
                "u": u_sub.flatten().tolist(),
                "v": v_sub.flatten().tolist()
            }
        }


sim_manager = SimulationManager()


@app.get("/")
async def get_index():
    """Serve main simulation frontend."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/status")
async def get_status():
    """Return status and telemetry summary."""
    async with sim_manager.lock:
        return {
            "running": sim_manager.running,
            "config": sim_manager.config.dict(),
            "telemetry": AerodynamicDiagnostics.get_summary_telemetry(sim_manager.solver)
            if sim_manager.solver else {}
        }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time bi-directional WebSocket connection with web dashboard."""
    await websocket.accept()

    async def receiver():
        try:
            while True:
                msg = await websocket.receive_json()
                action = msg.get("action")

                async with sim_manager.lock:
                    if action == "play":
                        sim_manager.running = True
                    elif action == "pause":
                        sim_manager.running = False
                    elif action == "step":
                        sim_manager.running = False
                        sim_manager.step_once = True
                    elif action == "reset":
                        sim_manager.setup_simulation()
                    elif action == "set_config":
                        for key, val in msg.get("config", {}).items():
                            if hasattr(sim_manager.config, key):
                                setattr(sim_manager.config, key, val)
                        sim_manager.setup_simulation()
                    elif action == "set_field":
                        sim_manager.config.display_field = msg.get("field", "vorticity")
        except Exception:
            pass

    async def sender():
        try:
            while True:
                async with sim_manager.lock:
                    if sim_manager.running or sim_manager.step_once:
                        for _ in range(2):
                            sim_manager.step()
                        sim_manager.step_once = False
                    payload = sim_manager.get_frame_payload()

                if payload:
                    await websocket.send_json(payload)
                await asyncio.sleep(0.033)
        except Exception:
            pass

    recv_task = asyncio.create_task(receiver())
    send_task = asyncio.create_task(sender())
    try:
        await asyncio.gather(recv_task, send_task)
    except Exception:
        pass
    finally:
        recv_task.cancel()
        send_task.cancel()
