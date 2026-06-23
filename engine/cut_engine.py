"""
Cut Engine — matches updated MATLAB cut functions exactly.

Key fix from updated MATLAB:
  interp2 orientation: theta_y is passed as COLUMN (rows→Y, cols→X).
  In NumPy/scipy: RegularGridInterpolator((theta_y, theta_x), grid)
  so the first axis of the grid is Y, second is X — which is exactly
  how eco_lin / ecx_lin are stored: shape (ny, nx).

Critical smoothness fix:
  Interpolation is done in LINEAR amplitude space, then converted to dB.
  Interpolating directly in dB space causes extreme spikes at deep nulls
  because a small linear difference near zero maps to huge dB swings.
"""

import numpy as np
from scipy.interpolate import RegularGridInterpolator

FLOOR_DB = -100.0   # fill / floor value in dB


# ── Grid extent ────────────────────────────────────────────────────────────

def grid_r_max(fd):
    """Symmetric radial extent of the loaded grid (deg)."""
    tx = fd['theta_x']
    ty = fd['theta_y']
    return float(min(abs(tx[0]), abs(tx[-1]), abs(ty[0]), abs(ty[-1])))


# ── Phi cut ────────────────────────────────────────────────────────────────

def phi_cut(fd, phi_deg, n_points=2000, r_max=None):
    """
    Sweep radially at fixed azimuth phi_deg.

    Returns
    -------
    r_vals   : (n_points,) signed distance from boresight [deg]
    eco_cut  : (n_points,) co-pol [dB]
    ecx_cut  : (n_points,) cross-pol [dB]
    """
    if r_max is None:
        r_max = grid_r_max(fd)

    r_vals = np.linspace(-r_max, r_max, n_points)
    ph = np.deg2rad(phi_deg)
    xq = r_vals * np.cos(ph)
    yq = r_vals * np.sin(ph)

    eco_lin = _interp2(fd, fd['eco_lin'], xq, yq, fill=0.0)
    ecx_lin = _interp2(fd, fd['ecx_lin'], xq, yq, fill=0.0)

    return r_vals, _to_db(eco_lin, fd), _to_db(ecx_lin, fd)


# ── Theta cut ──────────────────────────────────────────────────────────────

def theta_cut(fd, theta_deg, n_points=2000):
    """
    Sweep azimuth phi ∈ [-180, 180] at fixed elevation theta_deg.

    Returns
    -------
    phi_vals : (n_points,) phi angle [deg]
    eco_cut  : (n_points,) co-pol [dB]
    ecx_cut  : (n_points,) cross-pol [dB]
    """
    phi_vals = np.linspace(-180, 180, n_points)
    ph = np.deg2rad(phi_vals)
    xq = theta_deg * np.cos(ph)
    yq = theta_deg * np.sin(ph)

    eco_lin = _interp2(fd, fd['eco_lin'], xq, yq, fill=0.0)
    ecx_lin = _interp2(fd, fd['ecx_lin'], xq, yq, fill=0.0)

    return phi_vals, _to_db(eco_lin, fd), _to_db(ecx_lin, fd)


# ── Helpers ────────────────────────────────────────────────────────────────

def _interp2(fd, grid, xq, yq, fill=0.0):
    """
    Bilinear interpolation in linear amplitude space.
    grid shape: (ny, nx) — rows=theta_y, cols=theta_x.
    """
    tx = fd['theta_x']   # (nx,)
    ty = fd['theta_y']   # (ny,)

    interp = RegularGridInterpolator(
        (ty, tx), grid,
        method='linear',
        bounds_error=False,
        fill_value=fill,
    )
    pts = np.stack([yq, xq], axis=-1)   # (N, 2) — (y, x)
    return interp(pts)


def _to_db(lin, fd):
    """Convert linear amplitude to dB, clamped at floor."""
    floor = fd.get('floor', 1e-10)
    return 20.0 * np.log10(np.maximum(lin, floor))
