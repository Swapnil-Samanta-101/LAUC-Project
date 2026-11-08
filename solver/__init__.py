"""CFD Solver package: Core Navier-Stokes, Grid, Advection, Diffusion, Poisson."""

from .grid import MACGrid
from .ns_solver import NavierStokesSolver

__all__ = ["MACGrid", "NavierStokesSolver"]
