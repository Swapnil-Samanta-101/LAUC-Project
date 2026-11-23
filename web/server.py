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
from geometry.shapes import generate_flat_plate, generate_ellipse, generate_cylinder
from geometry.penalization import compute_polygon_mask, compute_circle_mask
from geometry.diagnostics import AerodynamicDiagnostics
from geometry.atmosphere import InternationalStandardAtmosphere
from geometry.polar_sweep import run_alpha_sweep

app = FastAPI(title="2D Navier-Stokes CFD Simulator")

# Static files path
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SimConfig(BaseModel):
    mode: str = "airfoil"  # "airfoil", "cascade", "cylinder", "cavity"
    shape_type: str = "naca"  # "naca", "flat_plate", "ellipse", "rotating_cylinder"
    naca_code: str = "0012"
    camber: float = 0.0  # 0.0 to 0.10 chord
    thickness: float = 0.12  # 0.02 to 0.25 chord
    spin_rate: float = 0.0  # rad/s (-4.0 to +4.0)
    alpha_deg: float = 4.0
    reynolds: float = 500.0
    airspeed: float = 40.0  # m/s
    altitude: float = 0.0  # meters
    wing_area: float = 1.0  # m^2
    chord_length: float = 1.0  # m
    resolution: str = "standard"  # "fast" (128x64), "standard" (192x96), "high" (256x128)
    display_field: str = "vorticity"  # "vorticity", "speed", "pressure", "divergence"
    speed_multiplier: int = 3  # physics steps per visual frame
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
        self._cached_poly_coords: Optional[List[List[List[float]]]] = None
        self._cached_cp: Dict[str, Any] = {}
        self._cached_cascade_metrics: Dict[str, Any] = {}
        self._frame_count: int = 0
        self.probe_coords: Optional[Tuple[float, float]] = None
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
        self._cached_poly_coords = None
        self._cached_cp = {}
        self._cached_cascade_metrics = {}
        self._frame_count = 0

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
            self._build_airfoil_solid()

    def _build_airfoil_solid(self) -> None:
        """Construct solid boundary mask and moving velocity fields for FoilSim geometries."""
        if self.solver is None or self.grid is None:
            return

        shape = self.config.shape_type
        ly = self.grid.ly
        y_center = ly / 2.0
        chord = 1.0
        x_origin = 1.5

        if shape == "flat_plate":
            poly = generate_flat_plate(
                chord=chord,
                x_le=x_origin,
                y_le=y_center,
                alpha_deg=self.config.alpha_deg,
                thickness=max(0.01, self.config.thickness)
            )
            self.polygons = [poly]
            mask = compute_polygon_mask(self.polygons, self.grid.X_c, self.grid.Y_c)
            self.solver.set_solid_mask(mask)

        elif shape == "ellipse":
            poly = generate_ellipse(
                chord=chord,
                x_le=x_origin,
                y_le=y_center,
                alpha_deg=self.config.alpha_deg,
                thickness_ratio=max(0.02, self.config.thickness)
            )
            self.polygons = [poly]
            mask = compute_polygon_mask(self.polygons, self.grid.X_c, self.grid.Y_c)
            self.solver.set_solid_mask(mask)

        elif shape == "rotating_cylinder":
            radius = 0.3
            center_x = 2.0
            center_y = y_center
            poly = generate_cylinder(radius=radius, center_x=center_x, center_y=center_y)
            self.polygons = [poly]

            mask_c = compute_circle_mask(center_x=center_x, center_y=center_y, radius=radius, X=self.grid.X_c, Y=self.grid.Y_c)
            mask_u = compute_circle_mask(center_x=center_x, center_y=center_y, radius=radius, X=self.grid.X_u, Y=self.grid.Y_u)
            mask_v = compute_circle_mask(center_x=center_x, center_y=center_y, radius=radius, X=self.grid.X_v, Y=self.grid.Y_v)

            omega = float(self.config.spin_rate)
            u_solid_f = -omega * (self.grid.Y_u - center_y) * mask_u
            v_solid_f = omega * (self.grid.X_v - center_x) * mask_v
            u_solid_c = -omega * (self.grid.Y_c - center_y) * mask_c
            v_solid_c = omega * (self.grid.X_c - center_x) * mask_c

            self.solver.set_solid_mask(mask_c, u_solid=u_solid_f, v_solid=v_solid_f, u_solid_c=u_solid_c, v_solid_c=v_solid_c)

        else:  # "naca"
            airfoil = NACA4Airfoil(
                code=self.config.naca_code,
                chord=chord,
                x_origin=x_origin,
                y_origin=y_center,
                alpha_deg=self.config.alpha_deg,
                camber=self.config.camber,
                thickness=self.config.thickness,
                n_points=120
            )
            self.polygons = [airfoil.polygon]
            mask = compute_polygon_mask(self.polygons, self.grid.X_c, self.grid.Y_c)
            self.solver.set_solid_mask(mask)

        self._cached_poly_coords = None

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Granular config update that avoids wiping flow fields on slider moves."""
        mode_changed = "mode" in new_config and new_config["mode"] != self.config.mode
        res_changed = "resolution" in new_config and new_config["resolution"] != self.config.resolution

        if mode_changed or res_changed or self.solver is None or self.grid is None:
            for key, val in new_config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, val)
            self.setup_simulation()
            return

        # 1. Update Reynolds number without resetting flow
        if "reynolds" in new_config:
            new_re = float(new_config["reynolds"])
            self.config.reynolds = new_re
            self.solver.re = new_re

        # 2. Update speed multiplier
        if "speed_multiplier" in new_config:
            self.config.speed_multiplier = max(1, min(10, int(new_config["speed_multiplier"])))

        # 3. Update display field
        if "display_field" in new_config:
            self.config.display_field = new_config["display_field"]

        # 4. Airfoil mode: update parameters dynamically without resetting velocity/pressure
        if self.config.mode == "airfoil":
            airfoil_keys = ["alpha_deg", "naca_code", "shape_type", "camber", "thickness", "spin_rate"]
            if any(k in new_config for k in airfoil_keys):
                for k in airfoil_keys:
                    if k in new_config:
                        setattr(self.config, k, new_config[k])
                self._build_airfoil_solid()

        # 5. Flight & atmospheric conditions update
        fc_keys = ["airspeed", "altitude", "wing_area", "chord_length"]
        if any(k in new_config for k in fc_keys):
            for k in fc_keys:
                if k in new_config:
                    setattr(self.config, k, float(new_config[k]))
            if new_config.get("auto_reynolds", False):
                fc = InternationalStandardAtmosphere.compute_flight_conditions(
                    altitude_m=self.config.altitude,
                    airspeed_mps=self.config.airspeed,
                    chord_m=self.config.chord_length,
                    wing_area_m2=self.config.wing_area
                )
                self.config.reynolds = min(2000.0, max(50.0, float(fc["reynolds"])))
                self.solver.re = self.config.reynolds

        # 6. Cascade mode: update parameters dynamically
        elif self.config.mode == "cascade":
            casc_keys = ["cascade_pitch", "cascade_stagger", "cascade_inlet_angle", "cascade_camber"]
            if any(k in new_config for k in casc_keys):
                for k in casc_keys:
                    if k in new_config:
                        setattr(self.config, k, new_config[k])
                u_in = float(np.cos(np.radians(self.config.cascade_inlet_angle)))
                v_in = float(np.sin(np.radians(self.config.cascade_inlet_angle)))
                self.solver.bc.u_inlet = u_in
                self.solver.bc.v_inlet = v_in
                cascade = TurbofanCascade(
                    chord=1.0,
                    pitch=float(self.config.cascade_pitch),
                    stagger_deg=float(self.config.cascade_stagger),
                    camber_code=str(self.config.cascade_camber),
                    domain_ly=self.grid.ly,
                    x_axial_pos=1.5,
                    inlet_flow_angle_deg=float(self.config.cascade_inlet_angle)
                )
                self.polygons = cascade.polygons
                self._cached_poly_coords = None
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

        # 3. Aerodynamic forces & surface Cp (cached across sub-frames for high FPS)
        fx, fy, cl, cd = self.solver.compute_aerodynamic_forces()
        self._frame_count += 1

        cp_data = self._cached_cp
        if self.config.mode == "airfoil" and (self._frame_count % 4 == 0 or not self._cached_cp):
            cp_dict = AerodynamicDiagnostics.extract_surface_cp(self.solver, x_le=1.5, chord=1.0, n_samples=35)
            self._cached_cp = {
                "x_c": cp_dict["x_c"].tolist(),
                "cp_upper": np.round(cp_dict["cp_upper"], 3).tolist(),
                "cp_lower": np.round(cp_dict["cp_lower"], 3).tolist(),
                "vectors": cp_dict.get("vectors", [])
            }
            cp_data = self._cached_cp

        cascade_metrics = self._cached_cascade_metrics
        if self.config.mode == "cascade" and (self._frame_count % 4 == 0 or not self._cached_cascade_metrics):
            self._cached_cascade_metrics = AerodynamicDiagnostics.compute_cascade_metrics(self.solver)
            cascade_metrics = self._cached_cascade_metrics

        # 4. Polygons in normalized coordinates [0, 1] for canvas overlay (cached)
        if self._cached_poly_coords is None:
            poly_coords = []
            for poly in self.polygons:
                poly_norm = poly.copy()
                poly_norm[:, 0] /= self.grid.lx
                poly_norm[:, 1] /= self.grid.ly
                poly_coords.append(np.round(poly_norm, 4).tolist())
            self._cached_poly_coords = poly_coords
        else:
            poly_coords = self._cached_poly_coords

        # 5. International Standard Atmosphere flight conditions & dimensional forces
        fc = InternationalStandardAtmosphere.compute_flight_conditions(
            altitude_m=self.config.altitude,
            airspeed_mps=self.config.airspeed,
            chord_m=self.config.chord_length,
            wing_area_m2=self.config.wing_area
        )
        lift_n, drag_n = InternationalStandardAtmosphere.compute_dimensional_forces(
            cl=cl, cd=cd, q_inf_pa=fc["q_inf_pa"], wing_area_m2=fc["wing_area_m2"]
        )

        # 6. Flow Probe local sampling if active
        probe_data = None
        if self.probe_coords is not None:
            px, py = self.probe_coords
            ix = int(np.clip(px * self.grid.nx, 0, self.grid.nx - 1))
            iy = int(np.clip(py * self.grid.ny, 0, self.grid.ny - 1))

            u_val = float(0.5 * (self.solver.u[iy, ix] + self.solver.u[iy, ix + 1]))
            v_val = float(0.5 * (self.solver.v[iy, ix] + self.solver.v[iy + 1, ix]))
            vel_mag = float(np.sqrt(u_val * u_val + v_val * v_val))
            vel_mps = vel_mag * fc["airspeed_mps"]

            p_val = float(self.solver.p[iy, ix])
            p_dim_pa = fc["pressure_pa"] + p_val * fc["q_inf_pa"]
            cp_val = 2.0 * p_val

            vort_grid = self.grid.compute_vorticity(self.solver.u, self.solver.v)
            vort_val = float(vort_grid[iy, ix])

            x_phys = px * self.grid.lx
            xc_val = (x_phys - 1.5) / 1.0  # chord is 1.0 starting at x_le=1.5
            in_solid = bool(self.solver.chi_c[iy, ix] > 0.4)

            probe_data = {
                "norm_x": round(px, 4),
                "norm_y": round(py, 4),
                "x_c": round(xc_val, 3),
                "vel_mag": round(vel_mag, 3),
                "vel_mps": round(vel_mps, 1),
                "p_coeff": round(cp_val, 3),
                "p_dim_pa": round(p_dim_pa, 1),
                "vorticity": round(vort_val, 2),
                "in_solid": in_solid
            }

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
            "lift_n": round(lift_n, 2),
            "drag_n": round(drag_n, 2),
            "flight_conditions": fc,
            "probe_data": probe_data,
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


class SweepRequest(BaseModel):
    shape_type: str = "naca"
    naca_code: str = "0012"
    camber: Optional[float] = None
    thickness: Optional[float] = None
    reynolds: float = 500.0
    alpha_start: float = -4.0
    alpha_end: float = 16.0
    alpha_step: float = 2.0


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


@app.post("/api/sweep/run")
async def run_sweep(req: SweepRequest):
    """Run an automated angle of attack sweep and return aerodynamic polars."""
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: run_alpha_sweep(
            shape_type=req.shape_type,
            naca_code=req.naca_code,
            camber=req.camber,
            thickness=req.thickness,
            reynolds=req.reynolds,
            alpha_start=req.alpha_start,
            alpha_end=req.alpha_end,
            alpha_step=req.alpha_step,
            steps_per_alpha=70,
            nx=96,
            ny=48
        )
    )
    return result


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
                        sim_manager.update_config(msg.get("config", {}))
                    elif action == "set_field":
                        sim_manager.config.display_field = msg.get("field", "vorticity")
                    elif action == "probe":
                        sim_manager.probe_coords = (float(msg.get("x", 0.5)), float(msg.get("y", 0.5)))
                    elif action == "clear_probe":
                        sim_manager.probe_coords = None
        except Exception:
            pass

    async def sender():
        try:
            while True:
                async with sim_manager.lock:
                    if sim_manager.running or sim_manager.step_once:
                        steps_to_run = sim_manager.config.speed_multiplier if sim_manager.running else 1
                        for _ in range(steps_to_run):
                            sim_manager.step()
                        sim_manager.step_once = False
                    payload = sim_manager.get_frame_payload()

                if payload:
                    await websocket.send_json(payload)
                await asyncio.sleep(0.02)
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
