"""Tests for NASA FoilSim Sweep and Flow Probe capabilities."""

import pytest
from fastapi.testclient import TestClient
from web.server import app, sim_manager


def test_api_status_contains_config():
    """Verify /api/status endpoint responds with configuration."""
    client = TestClient(app)
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "config" in data
    assert "running" in data
    assert data["config"]["mode"] in ["airfoil", "cascade", "cylinder", "cavity"]


def test_alpha_sweep_endpoint():
    """Verify POST /api/sweep/run returns lift curve and drag polar."""
    client = TestClient(app)
    payload = {
        "shape_type": "naca",
        "naca_code": "0012",
        "camber": 0.0,
        "thickness": 0.12,
        "reynolds": 200.0,
        "alpha_start": 0.0,
        "alpha_end": 4.0,
        "alpha_step": 2.0
    }
    response = client.post("/api/sweep/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "sweep_data" in data
    assert len(data["sweep_data"]) == 3  # 0, 2, 4 deg
    assert "cl_max" in data
    assert "stall_alpha" in data

    # Cl at 4 deg should be higher than Cl at 0 deg
    cl_0 = data["sweep_data"][0]["cl"]
    cl_4 = data["sweep_data"][2]["cl"]
    assert cl_4 > cl_0


def test_flow_probe_payload_sampling():
    """Verify probe_data sampling in frame payload when probe_coords is set."""
    sim_manager.setup_simulation()
    sim_manager.probe_coords = (0.25, 0.5)
    payload = sim_manager.get_frame_payload()
    assert "probe_data" in payload
    assert payload["probe_data"] is not None
    probe = payload["probe_data"]
    assert "vel_mag" in probe
    assert "vel_mps" in probe
    assert "p_coeff" in probe
    assert "p_dim_pa" in probe
    assert "vorticity" in probe
    assert "in_solid" in probe
    assert "x_c" in probe
    assert "lift_n" in payload
    assert "drag_n" in payload
    assert "flight_conditions" in payload
